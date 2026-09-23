from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.waste.models import WasteReport


class CollectionRequest(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        ACCEPTED = "accepted", "Accepted"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    waste_report = models.OneToOneField(
        WasteReport,
        on_delete=models.CASCADE,
        related_name="collection_request",
    )
    collector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="collections",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    actual_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.01)],
    )
    weight_unit = models.CharField(
        max_length=10,
        choices=WasteReport.WeightUnit.choices,
        default=WasteReport.WeightUnit.KILOGRAMS,
    )
    proof_photo = models.ImageField(upload_to="collection_proof/%Y/%m/", blank=True, null=True)
    notes = models.TextField(blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Collection request for {self.waste_report}"
