from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class WasteCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
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
    estimated_weight = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    weight_unit = models.CharField(max_length=10, choices=WeightUnit.choices, default=WeightUnit.KILOGRAMS)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    location_accuracy = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    photo = models.ImageField(upload_to="waste_reports/%Y/%m/", blank=True, null=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.category.name} report by {self.customer.username}"
