from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.decorators import approved_collector_required
from apps.waste.models import WasteReport

from .forms import CollectionCompletionForm
from .models import CollectionRequest


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
    collection = get_object_or_404(CollectionRequest.objects.select_for_update(), id=collection_id)

    if collection.collector_id != request.user.id:
        messages.error(request, "You can only complete collections assigned to you.")
        return redirect("collections_dashboard")

    if collection.status != CollectionRequest.Status.ACCEPTED:
        messages.error(request, "Only accepted collections can be completed.")
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

        messages.success(request, "Collection completed and the waste report is now marked as collected.")
        return redirect("collection_detail", collection_id=collection.id)

    return render(request, "collections/complete.html", {"form": form, "collection": collection})
