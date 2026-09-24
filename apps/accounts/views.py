from django.contrib import messages
from django.forms import modelformset_factory
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .analytics import dashboard_context
from .decorators import approved_collector_required, platform_admin_required
from .forms import (
    CollectorRegistrationForm,
    CustomerRegistrationForm,
    TakaPayAuthenticationForm,
)
from .models import CollectorProfile, User
from .operations_forms import MarketplacePreparationForm, RewardOperationsForm, TokenRateFormSet
from .services import set_collector_verification
from apps.cashout.models import CashOutRequest
from apps.collections.models import CollectionRequest
from apps.marketplace.models import BuyerRequest, MarketplaceMaterial
from apps.marketplace.services import transition_buyer_request
from apps.wallet.models import WalletTransaction
from apps.rewards.models import Reward, RewardRedemption
from apps.waste.models import WasteCategory


def register(request):
    form = CustomerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Account created successfully.")
        return redirect("login")
    return render(request, "accounts/register.html", {"form": form})


def collector_register(request):
    form = CollectorRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your collector application has been submitted and is awaiting verification.")
        return redirect("login")
    return render(request, "accounts/collector_register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = TakaPayAuthenticationForm(request, request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        messages.success(request, "Welcome to TakaPay.")
        return redirect("dashboard")
    return render(request, "accounts/login.html", {"form": form})


@login_required
def dashboard(request):
    if request.user.role == User.Role.COLLECTOR:
        profile = getattr(request.user, "collector_profile", None)
        if profile is None or profile.verification_status != profile.VerificationStatus.APPROVED:
            return render(request, "accounts/pending_verification.html")
        return redirect("collections_dashboard")
    if request.user.role == User.Role.ADMIN:
        return redirect("admin_analytics_dashboard")
    return render(request, "accounts/customer_dashboard.html")


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
    formset = TokenRateFormSet(request.POST or None, queryset=queryset, prefix="rates")
    if request.method == "POST" and formset.is_valid():
        formset.save()
        messages.success(request, "Token rates updated.")
        return redirect("admin_token_rates")
    return render(request, "accounts/operations/token_rates.html", {"formset": formset})


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
