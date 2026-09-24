from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import BuyerRequest, MarketplaceMaterial


def transition_buyer_request(buyer_request, new_status, admin_user, admin_notes=""):
    """Apply an allowed buyer-request transition and atomically update inventory on completion."""
    valid_transitions = {
        BuyerRequest.Status.PENDING: {
            BuyerRequest.Status.PROCESSING,
            BuyerRequest.Status.REJECTED,
            BuyerRequest.Status.CANCELLED,
        },
        BuyerRequest.Status.PROCESSING: {
            BuyerRequest.Status.COMPLETED,
            BuyerRequest.Status.REJECTED,
            BuyerRequest.Status.CANCELLED,
        },
    }

    with transaction.atomic():
        request = BuyerRequest.objects.select_for_update().get(pk=buyer_request.pk)
        if new_status not in valid_transitions.get(request.status, set()):
            raise ValidationError(f"Cannot move a {request.get_status_display()} request to {new_status}.")

        if new_status == BuyerRequest.Status.COMPLETED:
            material = MarketplaceMaterial.objects.select_for_update().get(pk=request.material_id)
            if material.available_quantity < request.requested_quantity:
                raise ValidationError("There is not enough material available to complete this request.")
            material.available_quantity -= request.requested_quantity
            material.save(update_fields=["available_quantity", "updated_at"])

        request.status = new_status
        request.admin_notes = admin_notes
        if new_status in {
            BuyerRequest.Status.COMPLETED,
            BuyerRequest.Status.REJECTED,
            BuyerRequest.Status.CANCELLED,
        }:
            request.processed_at = timezone.now()
            request.processed_by = admin_user
        request.save(update_fields=["status", "admin_notes", "processed_at", "processed_by"])

    buyer_request.refresh_from_db()
    return buyer_request


def complete_buyer_request(buyer_request, admin_user, admin_notes=""):
    """Complete a processable buyer request using the same inventory-safe transition."""
    return transition_buyer_request(
        buyer_request,
        BuyerRequest.Status.COMPLETED,
        admin_user,
        admin_notes,
    )
