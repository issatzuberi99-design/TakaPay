from django.core.exceptions import ValidationError
from django.db import transaction

from .models import CollectorProfile, User


@transaction.atomic
def set_collector_verification(profile_id, status):
    valid_statuses = {value for value, _ in CollectorProfile.VerificationStatus.choices}
    if status not in valid_statuses:
        raise ValidationError("Choose a valid collector verification status.")
    profile = CollectorProfile.objects.select_for_update().get(pk=profile_id)
    user = User.objects.select_for_update().get(pk=profile.user_id)
    profile.verification_status = status
    profile.save(update_fields=("verification_status", "updated_at"))
    user.collector_verification_status = status
    user.save(update_fields=("collector_verification_status",))
    return profile
