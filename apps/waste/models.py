from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.validators import MaxValueValidator, MinValueValidator


class WasteCategory(models.Model):
    class RewardUnit(models.TextChoices):
        KILOGRAM = "kg", "Kilogram (KG)"
        PIECE = "piece", "Piece"

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    reward_unit = models.CharField(
        max_length=10,
        choices=RewardUnit.choices,
        default=RewardUnit.KILOGRAM,
    )
    token_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Waste categories"

    def __str__(self):
        return self.name


class WasteReport(models.Model):
    class WeightUnit(models.TextChoices):
        KILOGRAMS = "kg", "Kilograms"
        GRAMS = "g", "Grams"

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        PENDING_COLLECTION = "pending_collection", "Pending collection"
        COLLECTED = "collected", "Collected"
        VERIFIED = "verified", "Verified"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="waste_reports",
    )
    category = models.ForeignKey(WasteCategory, on_delete=models.PROTECT, related_name="reports")
    description = models.TextField()
    estimated_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0.01)])
    weight_unit = models.CharField(max_length=10, choices=WeightUnit.choices, default=WeightUnit.KILOGRAMS)
    estimated_piece_count = models.DecimalField(
        max_digits=10, decimal_places=0, null=True, blank=True, validators=[MinValueValidator(1)],
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    location_accuracy = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    photo = models.ImageField(upload_to="waste_reports/%Y/%m/", blank=True, null=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=Q(estimated_piece_count__isnull=True) | Q(estimated_piece_count__gte=1),
                name="waste_report_piece_estimate_must_be_positive",
            ),
        ]

    def __str__(self):
        return f"{self.category.name} report by {self.customer.username}"
