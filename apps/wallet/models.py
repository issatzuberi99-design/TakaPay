from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum


class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def balance(self):
        total = self.transactions.aggregate(total=Sum("amount"))["total"]
        return total if total is not None else Decimal("0.00")

    def __str__(self):
        return f"Wallet for {self.user.username}"


class WalletTransaction(models.Model):
    class TransactionType(models.TextChoices):
        COLLECTION_REWARD = "collection_reward", "Collection reward"
        REWARD_REDEMPTION = "reward_redemption", "Reward redemption"
        CASHOUT = "cashout", "Cash-out"
        ADJUSTMENT = "adjustment", "Adjustment"

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=100, blank=True, db_index=True)
    collection_reward_unit = models.CharField(
        max_length=10,
        choices=(("kg", "Kilogram (KG)"), ("piece", "Piece")),
        null=True,
        blank=True,
    )
    collection_reward_quantity = models.DecimalField(max_digits=15, decimal_places=5, null=True, blank=True)
    collection_reward_rate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    collection_reward_material = models.CharField(max_length=150, blank=True)
    collection = models.OneToOneField(
        "collections.CollectionRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reward_transaction",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(transaction_type="collection_reward")
                    | Q(
                        transaction_type__in=["reward_redemption", "cashout", "adjustment"],
                        collection__isnull=True,
                    )
                ),
                name="wallet_transaction_collection_usage_is_valid",
            )
        ]

    def clean(self):
        if self.transaction_type == self.TransactionType.COLLECTION_REWARD:
            snapshot_fields = (
                self.collection_reward_unit,
                self.collection_reward_quantity,
                self.collection_reward_rate,
                self.collection_reward_material,
            )
            if any(snapshot_fields) and not all(snapshot_fields):
                raise ValidationError("Collection reward snapshots must include unit, quantity, rate, and material.")
        elif any((self.collection_reward_unit, self.collection_reward_quantity, self.collection_reward_rate, self.collection_reward_material)):
            raise ValidationError("Only collection reward transactions can store collection reward snapshots.")
        if self.transaction_type in {
            self.TransactionType.REWARD_REDEMPTION,
            self.TransactionType.CASHOUT,
            self.TransactionType.ADJUSTMENT,
        } and self.collection_id is not None:
            raise ValidationError({"collection": "Only collection reward transactions can reference a collection."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transaction_type} {self.amount} for {self.wallet.user.username}"
