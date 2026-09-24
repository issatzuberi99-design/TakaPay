from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.waste.models import WasteCategory


class MarketplaceMaterial(models.Model):
    class Unit(models.TextChoices):
        KILOGRAM = "kg", "Kilograms"
        TON = "ton", "Tonnes"
        PIECE = "piece", "Pieces"

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        WasteCategory,
        on_delete=models.PROTECT,
        related_name="marketplace_materials",
        null=True,
        blank=True,
    )
    image = models.ImageField(upload_to="marketplace/materials/%Y/%m/", blank=True)
    available_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.KILOGRAM)
    price_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-active", "name"]
        indexes = [models.Index(fields=["active", "category"])]

    def __str__(self):
        return self.name


class BuyerRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    buyer_name = models.CharField(max_length=150)
    company_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    material = models.ForeignKey(
        MarketplaceMaterial,
        on_delete=models.PROTECT,
        related_name="buyer_requests",
    )
    requested_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    unit = models.CharField(max_length=10, choices=MarketplaceMaterial.Unit.choices, default=MarketplaceMaterial.Unit.KILOGRAM)
    material_name = models.CharField(max_length=150, blank=True, default="")
    price_per_unit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    admin_notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="processed_buyer_requests")

    class Meta:
        ordering = ["-requested_at"]

    def transition_to(self, new_status, admin_user, admin_notes=""):
        from .services import transition_buyer_request

        return transition_buyer_request(self, new_status, admin_user, admin_notes)

    def __str__(self):
        return f"{self.buyer_name} - {self.material_name}"
