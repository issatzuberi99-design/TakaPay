from django.db import models


class MarketplaceMaterial(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    available_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = models.CharField(max_length=30, default="kg")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class BuyerRequest(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_REVIEW = "in_review", "In review"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    buyer_name = models.CharField(max_length=150)
    company = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    requested_material = models.ForeignKey(
        MarketplaceMaterial,
        on_delete=models.PROTECT,
        related_name="buyer_requests",
    )
    requested_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.buyer_name} - {self.requested_material.name}"
