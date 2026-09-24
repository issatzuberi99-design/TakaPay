from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.decorators import approved_collector_required
from apps.wallet.models import Wallet, WalletTransaction
from apps.waste.models import WasteReport

from .forms import CollectionCompletionForm
from .models import CollectionRequest


def _convert_weight_to_kg(weight, unit):
    if unit == WasteReport.WeightUnit.KILOGRAMS:
        return weight
    if unit == WasteReport.WeightUnit.GRAMS:
        return weight / Decimal("1000")
    return weight


def _calculate_collection_reward(collection):
    if collection.waste_report.category.token_rate_per_kg <= 0:
        return Decimal("0.00")
    kilograms = _convert_weight_to_kg(collection.actual_weight, collection.weight_unit)
    reward = kilograms * collection.waste_report.category.token_rate_per_kg
    return reward.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@approved_collector_required
def collections_dashboard(request):
    available_collections = CollectionRequest.objects.filter(
        status=CollectionRequest.Status.AVAILABLE,
    ).select_related("waste_report__category", "waste_report__customer")
    my_collections = CollectionRequest.objects.filter(
        collector=request.user,
    ).select_related("waste_report__category").order_by("-accepted_at", "-created_at")
    return render(
        request,
        "collections/dashboard.html",
        {"available_collections": available_collections, "my_collections": my_collections},
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

    if WalletTransaction.objects.filter(collection=collection).exists():
        messages.error(request, "This collection has already generated a token reward.")
        return redirect("collection_detail", collection_id=collection.id)

    form = CollectionCompletionForm(request.POST or None, request.FILES or None, instance=collection)
    if request.method == "POST" and form.is_valid():
        collection = form.save(commit=False)
        collection.status = CollectionRequest.Status.COMPLETED
        collection.completed_at = timezone.now()
        collection.save()

        report = collection.waste_report
        report.status = WasteReport.Status.COLLECTED
        report.save(update_fields=["status", "updated_at"])

        reward_amount = _calculate_collection_reward(collection)
        wallet, _ = Wallet.objects.get_or_create(user=collection.waste_report.customer)
        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type=WalletTransaction.TransactionType.COLLECTION_REWARD,
            amount=reward_amount,
            description=f"Collection reward for {report.category.name}",
            reference=f"collection-reward-{collection.id}",
            collection=collection,
        )

        messages.success(request, "Collection completed and the customer wallet was credited with tokens.")
        return redirect("collection_detail", collection_id=collection.id)

    return render(request, "collections/complete.html", {"form": form, "collection": collection})
