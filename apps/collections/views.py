
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.decorators import approved_collector_required
from apps.wallet.models import Wallet, WalletTransaction
from apps.marketplace.models import MarketplaceMaterial
from apps.waste.models import WasteCategory, WasteReport
from apps.economics.models import EconomicPolicy, MaterialRate
from apps.economics.services import collector_wallet_for, settle_collection

from .forms import CollectionCompletionForm
from .rewards import calculate_collection_reward
from .models import CollectionRequest


@approved_collector_required
def collections_dashboard(request):
    available_collections = CollectionRequest.objects.filter(
        status=CollectionRequest.Status.AVAILABLE,
    ).select_related("waste_report__category", "waste_report__customer")
    my_collections = CollectionRequest.objects.filter(
        collector=request.user,
    ).select_related("waste_report__category").order_by("-accepted_at", "-created_at")
    wallet = collector_wallet_for(request.user)
    return render(
        request,
        "collections/dashboard.html",
        {
            "available_collections": available_collections,
            "my_collections": my_collections,
            "wallet": wallet,
        },
    )


@approved_collector_required
def collection_detail(request, collection_id):
    collection = get_object_or_404(
        CollectionRequest.objects.select_related(
            "waste_report__category",
            "waste_report__customer",
            "collector",
        ),
        id=collection_id,
    )
    return render(request, "collections/detail.html", {"collection": collection})


@approved_collector_required
@transaction.atomic
def accept_collection(request, collection_id):
    if request.method != "POST":
        return redirect("collection_detail", collection_id=collection_id)

    collection = get_object_or_404(CollectionRequest.objects.select_for_update(), id=collection_id)

    if collection.status != CollectionRequest.Status.AVAILABLE:
        messages.error(request, "This collection request is no longer available.")
        return redirect("collection_detail", collection_id=collection.id)

    collection.collector = request.user
    collection.status = CollectionRequest.Status.ACCEPTED
    collection.accepted_at = timezone.now()
    collection.save(update_fields=["collector", "status", "accepted_at", "updated_at"])

    report = collection.waste_report
    report.status = WasteReport.Status.PENDING_COLLECTION
    report.save(update_fields=["status", "updated_at"])

    messages.success(request, "Collection accepted successfully.")
    return redirect("collection_detail", collection_id=collection.id)


@approved_collector_required
@transaction.atomic
def complete_collection(request, collection_id):
    collection = get_object_or_404(CollectionRequest.objects.select_for_update().select_related("waste_report__category", "waste_report__customer"), id=collection_id)

    if collection.collector_id != request.user.id:
        messages.error(request, "You can only complete collections assigned to you.")
        return redirect("collections_dashboard")

    if collection.status != CollectionRequest.Status.ACCEPTED:
        messages.error(request, "Only accepted collections can be completed.")
        return redirect("collection_detail", collection_id=collection.id)

    if WalletTransaction.objects.filter(collection=collection).exists() or hasattr(collection, "economic_settlement"):
        messages.error(request, "This collection has already been settled.")
        return redirect("collection_detail", collection_id=collection.id)

    category = collection.waste_report.category
    if request.method == "POST":
        category = WasteCategory.objects.select_for_update().get(pk=collection.waste_report.category_id)
    form = CollectionCompletionForm(
        request.POST or None,
        request.FILES or None,
        instance=collection,
        category=category,
    )
    if request.method == "POST" and category.token_rate <= 0:
        form.add_error(None, "This material has no positive token rate. Ask an administrator to configure its rate before completing the collection.")
    if request.method == "POST" and form.is_valid():
        collection = form.save(commit=False)
        if category.reward_unit == WasteCategory.RewardUnit.KILOGRAM:
            collection.actual_weight = form.cleaned_data["actual_weight"]
            collection.weight_unit = form.cleaned_data["weight_unit"]
        else:
            collection.actual_piece_count = form.cleaned_data["actual_piece_count"]
        collection.proof_photo = form.cleaned_data["proof_photo"]
        collection.notes = form.cleaned_data["notes"]
        collection.save()
        try:
            reward = calculate_collection_reward(collection, category)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            category = collection.waste_report.category
            has_economic_configuration = EconomicPolicy.applicable(category.pk, timezone.now()) and MaterialRate.objects.filter(
                category=category, active=True, effective_from__lte=timezone.now(),
            ).exists()
            if has_economic_configuration:
                try:
                    settle_collection(collection)
                except ValidationError as error:
                    form.add_error(None, error)
                else:
                    messages.success(request, "Collection settled, tokens and collector earnings credited, and material sent to the preparation queue.")
                    return redirect("collection_detail", collection_id=collection.id)
            else:
                collection.status = CollectionRequest.Status.COMPLETED
                collection.completed_at = timezone.now()
                collection.save()

                report = collection.waste_report
                report.status = WasteReport.Status.COLLECTED
                report.save(update_fields=["status", "updated_at"])

                wallet, _ = Wallet.objects.get_or_create(user=report.customer)
                wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type=WalletTransaction.TransactionType.COLLECTION_REWARD,
                    amount=reward.amount,
                    description=f"Collection reward for {reward.material}",
                    reference=f"collection-reward-{collection.id}",
                    collection=collection,
                    collection_reward_unit=reward.unit,
                    collection_reward_quantity=reward.quantity,
                    collection_reward_rate=reward.rate,
                    collection_reward_material=reward.material,
                )
                material_unit = MarketplaceMaterial.Unit.PIECE if reward.unit == WasteCategory.RewardUnit.PIECE else MarketplaceMaterial.Unit.KILOGRAM
                MarketplaceMaterial.objects.create(
                    name=report.category.name, description="", category=report.category,
                    available_quantity=reward.quantity, unit=material_unit, active=False,
                    preparation_status=MarketplaceMaterial.PreparationStatus.READY, source_collection=collection,
                )
                messages.success(request, "Collection completed, tokens credited, and material sent to the preparation queue.")
                return redirect("collection_detail", collection_id=collection.id)

    return render(request, "collections/complete.html", {"form": form, "collection": collection})
