from django.contrib import messages
from django.forms import modelformset_factory
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Sum

from .analytics import dashboard_context
from .decorators import approved_collector_required, platform_admin_required
from .forms import (
    CollectorRegistrationForm,
    CustomerRegistrationForm,
    TakaPayAuthenticationForm,
)
from .models import CollectorProfile, User
from .operations_forms import (
    CollectorBonusForm,
    EconomicPolicyForm,
    EconomicSettingForm,
    MarketplacePreparationForm,
    MaterialRateForm,
    RewardOperationsForm,
    TokenRateFormSet,
    CashOutRateForm,
    WasteCategoryCreateForm,
)
from .services import set_collector_verification
from apps.cashout.models import CashOutRequest
from apps.cashout.models import CashOutRate
from apps.collections.models import CollectionRequest
from apps.wallet.models import Wallet
from apps.waste.models import WasteReport
from apps.marketplace.models import BuyerRequest, MarketplaceMaterial
from apps.marketplace.services import transition_buyer_request
from apps.wallet.models import WalletTransaction
from apps.rewards.models import Reward, RewardRedemption
from apps.waste.models import WasteCategory
from apps.economics.models import CollectorBonus, CollectorPayout, CollectorWallet, EconomicPolicy, EconomicSettlement, EconomicSetting, MaterialRate


MODEL_BACKEND = "django.contrib.auth.backends.ModelBackend"


def _safe_next_url(request):
    """Return ?next=... only when it points back to this site."""
    target = request.GET.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return ""


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = CustomerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend=MODEL_BACKEND)
        messages.success(request, "Welcome to TakaPay! Your account is ready.")
        return redirect("dashboard")
    return render(request, "accounts/register.html", {"form": form})


def collector_register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = CollectorRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend=MODEL_BACKEND)
        messages.success(request, "Application submitted. We will review it and update you here.")
        return redirect("dashboard")
    return render(request, "accounts/collector_register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = TakaPayAuthenticationForm(request, request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        messages.success(request, "Welcome to TakaPay.")
        return redirect(_safe_next_url(request) or "dashboard")
    return render(request, "accounts/login.html", {"form": form})


@login_required
def dashboard(request):
    if request.user.role == User.Role.COLLECTOR:
        profile = getattr(request.user, "collector_profile", None)
        status = profile.verification_status if profile else CollectorProfile.VerificationStatus.PENDING
        if status != CollectorProfile.VerificationStatus.APPROVED:
            return render(request, "accounts/pending_verification.html", {"application_status": status})
        return redirect("collections_dashboard")
    if request.user.role == User.Role.ADMIN:
        return redirect("admin_analytics_dashboard")

    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    recent_reports = (
        WasteReport.objects.filter(customer=request.user)
        .select_related("category")
        .order_by("-created_at")[:5]
    )
    total_recycled_kg = CollectionRequest.objects.filter(
        waste_report__customer=request.user,
        status=CollectionRequest.Status.COMPLETED,
        weight_unit=WasteReport.WeightUnit.KILOGRAMS,
    ).aggregate(total=Sum("actual_weight"))["total"]

    return render(request, "accounts/customer_dashboard.html", {
        "wallet": wallet,
        "recent_reports": recent_reports,
        "recent_transactions": wallet.transactions.all()[:5],
        "total_recycled_kg": total_recycled_kg,
    })


@approved_collector_required
def collector_jobs(request):
    return redirect("collections_dashboard")


@login_required
def admin_analytics_dashboard(request):
    can_view = request.user.is_active and (
        request.user.is_staff
        or request.user.is_superuser
        or request.user.role == User.Role.ADMIN
    )
    if not can_view:
        raise PermissionDenied
    return render(request, "accounts/admin_dashboard.html", dashboard_context(request))


@login_required
def admin_dashboard(request):
    if not (
        request.user.is_staff
        or request.user.is_superuser
        or request.user.role == User.Role.ADMIN
    ):
        raise PermissionDenied
    return redirect("admin_analytics_dashboard")


@platform_admin_required
def admin_token_rates(request):
    queryset = WasteCategory.objects.all().order_by("name")
    category_form = WasteCategoryCreateForm(request.POST or None, prefix="category")
    if request.method == "POST" and request.POST.get("form_type") == "category":
        if category_form.is_valid():
            category_form.save()
            messages.success(request, "Waste category created.")
            return redirect("admin_token_rates")
    formset = TokenRateFormSet(request.POST or None, queryset=queryset, prefix="rates")
    if request.method == "POST" and formset.is_valid():
        formset.save()
        messages.success(request, "Token rates updated.")
        return redirect("admin_token_rates")
    return render(request, "accounts/operations/token_rates.html", {"formset": formset, "category_form": category_form})


@platform_admin_required
def marketplace_preparation(request):
    materials = MarketplaceMaterial.objects.filter(source_collection__isnull=False).select_related(
        "category", "source_collection__waste_report", "source_collection__waste_report__category",
    )
    return render(request, "accounts/operations/marketplace_preparation.html", {"materials": materials})


@platform_admin_required
def marketplace_preparation_edit(request, material_id):
    material = get_object_or_404(
        MarketplaceMaterial.objects.filter(source_collection__isnull=False).select_related("source_collection__waste_report"),
        pk=material_id,
    )
    form = MarketplacePreparationForm(request.POST or None, request.FILES or None, instance=material)
    if request.method == "POST" and form.is_valid():
        material = form.save(commit=False)
        material.active = material.preparation_status == MarketplaceMaterial.PreparationStatus.PUBLISHED
        material.prepared_by = request.user
        if material.preparation_status == MarketplaceMaterial.PreparationStatus.PUBLISHED and material.published_at is None:
            material.published_at = timezone.now()
        material.save()
        messages.success(request, "Marketplace preparation saved.")
        return redirect("marketplace_preparation")
    return render(request, "accounts/operations/marketplace_preparation_edit.html", {"form": form, "material": material})


@platform_admin_required
def admin_rewards(request):
    rewards = Reward.objects.all()
    return render(request, "accounts/operations/rewards.html", {"rewards": rewards})


@platform_admin_required
def admin_reward_edit(request, reward_id=None):
    reward = get_object_or_404(Reward, pk=reward_id) if reward_id is not None else None
    form = RewardOperationsForm(request.POST or None, request.FILES or None, instance=reward)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Reward saved.")
        return redirect("admin_rewards")
    return render(request, "accounts/operations/reward_edit.html", {"form": form, "reward": reward})


@platform_admin_required
def admin_redemptions(request):
    redemptions = RewardRedemption.objects.select_related("customer", "reward")
    return render(request, "accounts/operations/redemptions.html", {"redemptions": redemptions})


@platform_admin_required
def admin_economics(request, section="overview"):
    valid_sections = {"overview", "policies", "rates", "bonuses", "wallets", "payouts", "settlements", "settings", "cashout-rates"}
    if section not in valid_sections:
        section = "overview"
    forms = {
        "policy": EconomicPolicyForm(prefix="policy"),
        "rate": MaterialRateForm(prefix="rate"),
        "bonus": CollectorBonusForm(prefix="bonus"),
        "settings": EconomicSettingForm(instance=EconomicSetting.current(), prefix="settings"),
        "cashout_rate": CashOutRateForm(prefix="cashout_rate"),
    }
    if request.method == "POST":
        form_key = request.POST.get("form_type")
        form_map = {"policy": EconomicPolicyForm, "rate": MaterialRateForm, "bonus": CollectorBonusForm, "cashout_rate": CashOutRateForm}
        if form_key in form_map:
            instance = None
            if form_key == "rate":
                instance = MaterialRate.objects.filter(category_id=request.POST.get("rate-category")).first()
            form = form_map[form_key](request.POST, prefix=form_key, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, f"Economic {form_key} saved.")
                if form_key == "cashout_rate" and form.instance.active:
                    CashOutRate.objects.exclude(pk=form.instance.pk).filter(active=True).update(active=False)
                return redirect("admin_economics_section", section={"policy": "policies", "rate": "rates", "bonus": "bonuses", "cashout_rate": "cashout-rates"}[form_key])
            forms[form_key] = form
        elif form_key == "settings":
            form = EconomicSettingForm(request.POST, instance=EconomicSetting.current(), prefix="settings")
            if form.is_valid():
                form.save()
                messages.success(request, "Economic thresholds updated.")
                return redirect("admin_economics_section", section="settings")
            forms["settings"] = form
    return render(request, "accounts/operations/economics.html", {
        "section": section,
        "forms": forms,
        "policies": EconomicPolicy.objects.select_related("category").all(),
        "rates": MaterialRate.objects.select_related("category").all(),
        "bonuses": CollectorBonus.objects.all(),
        "wallets": CollectorWallet.objects.select_related("user").all(),
        "payouts": CollectorPayout.objects.select_related("collector", "processed_by").all(),
        "settlements": EconomicSettlement.objects.select_related("collection", "category", "policy").all(),
        "settings_record": EconomicSetting.current(),
        "cashout_rates": CashOutRate.objects.all(),
    })


@platform_admin_required
def admin_collector_payout_transition(request, payout_id):
    if request.method == "POST":
        payout = get_object_or_404(CollectorPayout, pk=payout_id)
        try:
            payout.transition_to(request.POST.get("status"), request.user, request.POST.get("admin_notes", ""))
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, "Collector payout updated.")
    return redirect("admin_economics_section", section="payouts")


def _admin_collection_rows(queryset):
    rows = []
    for collection in queryset:
        rows.append({
            "collection": collection,
            "reward": getattr(collection, "reward_transaction", None),
            "preparation": getattr(collection, "marketplace_material", None),
        })
    return rows


def _collection_operations(request, *, history=False):
    queryset = CollectionRequest.objects.select_related(
        "collector", "waste_report__customer", "waste_report__category",
    ).prefetch_related("reward_transaction", "marketplace_material")
    if history:
        queryset = queryset.filter(status=CollectionRequest.Status.COMPLETED)
    else:
        status = request.GET.get("status", "")
        valid_statuses = {value for value, _ in CollectionRequest.Status.choices}
        if status in valid_statuses:
            queryset = queryset.filter(status=status)
    date_from = parse_date(request.GET.get("from", ""))
    date_to = parse_date(request.GET.get("to", ""))
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return render(request, "accounts/operations/collection_operations.html", {
        "rows": _admin_collection_rows(queryset), "history": history,
        "statuses": CollectionRequest.Status.choices,
        "selected_status": request.GET.get("status", ""),
        "date_from": request.GET.get("from", ""), "date_to": request.GET.get("to", ""),
    })


@platform_admin_required
def admin_collection_requests(request):
    return _collection_operations(request)


@platform_admin_required
def admin_collection_history(request):
    return _collection_operations(request, history=True)


@platform_admin_required
def collector_applications(request):
    from django.db.models import Case, IntegerField, When
    profiles = CollectorProfile.objects.select_related("user").order_by(
        Case(
            When(verification_status=CollectorProfile.VerificationStatus.PENDING, then=0),
            default=1,
            output_field=IntegerField(),
        ),
        "-created_at",
    )
    status = request.GET.get("status", "")
    if status in {value for value, _ in CollectorProfile.VerificationStatus.choices}:
        profiles = profiles.filter(verification_status=status)
    return render(request, "accounts/operations/collector_applications.html", {
        "profiles": profiles, "statuses": CollectorProfile.VerificationStatus.choices,
        "selected_status": status,
    })


@platform_admin_required
def collector_application_detail(request, profile_id):
    profile = get_object_or_404(CollectorProfile.objects.select_related("user"), pk=profile_id)
    if request.method == "POST":
        status = request.POST.get("status")
        if status not in {CollectorProfile.VerificationStatus.APPROVED, CollectorProfile.VerificationStatus.REJECTED}:
            messages.error(request, "Choose approve or reject for this application.")
        else:
            set_collector_verification(profile.pk, status)
            messages.success(request, f"Collector application {status}.")
            return redirect("collector_application_detail", profile_id=profile.pk)
    return render(request, "accounts/operations/collector_application_detail.html", {"profile": profile})


@platform_admin_required
def admin_wallet_activity(request):
    transactions = WalletTransaction.objects.select_related("wallet__user", "collection").order_by("-created_at")
    return render(request, "accounts/operations/wallet_activity.html", {"transactions": transactions})


@platform_admin_required
def admin_published_materials(request):
    materials = MarketplaceMaterial.objects.filter(
        preparation_status=MarketplaceMaterial.PreparationStatus.PUBLISHED,
    ).select_related("category").order_by("-published_at")
    return render(request, "accounts/operations/published_materials.html", {"materials": materials})


@platform_admin_required
def admin_buyer_requests(request):
    requests = BuyerRequest.objects.select_related("material", "processed_by").order_by("-requested_at")
    return render(request, "accounts/operations/buyer_requests.html", {"requests": requests})


@platform_admin_required
def admin_buyer_request_transition(request, request_id):
    if request.method != "POST":
        return redirect("admin_buyer_requests")
    buyer_request = get_object_or_404(BuyerRequest, pk=request_id)
    try:
        transition_buyer_request(
            buyer_request, request.POST.get("status"), request.user,
            request.POST.get("admin_notes", ""),
        )
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, "Buyer request updated.")
    return redirect("admin_buyer_requests")


@platform_admin_required
def admin_cashout_requests(request):
    requests = CashOutRequest.objects.select_related("customer", "processed_by").order_by("-requested_at")
    return render(request, "accounts/operations/cashout_requests.html", {"requests": requests})


@platform_admin_required
def admin_cashout_transition(request, request_id):
    if request.method != "POST":
        return redirect("admin_cashout_requests")
    cashout = get_object_or_404(CashOutRequest, pk=request_id)
    try:
        cashout.transition_to(
            request.POST.get("status"), request.user,
            request.POST.get("admin_notes", ""),
        )
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, "Cash-out request updated.")
    return redirect("admin_cashout_requests")