from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.collections.models import CollectionRequest
from apps.marketplace.models import MarketplaceMaterial
from apps.waste.models import WasteCategory


class EconomicSetting(models.Model):
    customer_cashout_min_tokens = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("10000.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    collector_payout_min_tzs = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("10000.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.pk and type(self).objects.exclude(pk=self.pk).exists():
            raise ValidationError("Only one economic settings record is allowed.")

    @classmethod
    def current(cls):
        settings_record, _ = cls.objects.get_or_create(pk=1)
        return settings_record


class EconomicPolicy(models.Model):
    name = models.CharField(max_length=150)
    category = models.ForeignKey(
        WasteCategory, on_delete=models.PROTECT, null=True, blank=True,
        related_name="economic_policies",
    )
    customer_percent = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    collector_percent = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    operations_percent = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    active = models.BooleanField(default=True)
    effective_from = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_from", "-created_at"]
        constraints = [
            models.CheckConstraint(
                check=Q(customer_percent__gte=0) & Q(collector_percent__gte=0) & Q(operations_percent__gte=0),
                name="economic_policy_percentages_nonnegative",
            ),
        ]

    def clean(self):
        total = (self.customer_percent or Decimal("0")) + (self.collector_percent or Decimal("0")) + (self.operations_percent or Decimal("0"))
        if total != Decimal("100.00"):
            raise ValidationError("Customer, collector, and operations percentages must total exactly 100%.")

    @classmethod
    def applicable(cls, category_id, at):
        return cls.objects.filter(
            Q(category_id=category_id) | Q(category__isnull=True),
            active=True,
            effective_from__lte=at,
        ).order_by(models.F("category_id").desc(nulls_last=True), "-effective_from", "-created_at").first()

    def __str__(self):
        return f"{self.name} ({self.customer_percent}/{self.collector_percent}/{self.operations_percent})"


class MaterialRate(models.Model):
    category = models.OneToOneField(WasteCategory, on_delete=models.PROTECT, related_name="material_rate")
    rate_per_unit = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    currency = models.CharField(max_length=10, default="TZS")
    active = models.BooleanField(default=True)
    effective_from = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.category.name}: {self.rate_per_unit} {self.currency}/{self.category.get_reward_unit_display()}"


class CollectorWallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="collector_wallet")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def balance(self):
        from django.db.models import Sum
        total = self.transactions.aggregate(total=Sum("amount"))["total"]
        return total if total is not None else Decimal("0.00")

    def __str__(self):
        return f"Collector wallet for {self.user.username}"


class CollectorWalletTransaction(models.Model):
    class TransactionType(models.TextChoices):
        COLLECTION_EARNING = "collection_earning", "Collection earning"
        BONUS = "bonus", "Bonus"
        ADJUSTMENT = "adjustment", "Adjustment"
        PAYOUT = "payout", "Payout"
        REFUND = "refund", "Refund"

    collector_wallet = models.ForeignKey(CollectorWallet, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    collection = models.ForeignKey(CollectionRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name="collector_transactions")
    payout = models.ForeignKey("CollectorPayout", on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")
    reference = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(check=~Q(amount=0), name="collector_transaction_amount_nonzero"),
            models.CheckConstraint(
                check=Q(transaction_type="collection_earning", collection__isnull=False)
                | Q(transaction_type="bonus", collection__isnull=False)
                | Q(transaction_type__in=["adjustment", "payout", "refund"]),
                name="collector_transaction_collection_usage_valid",
            ),
        ]


class CollectorBonus(models.Model):
    name = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    active = models.BooleanField(default=True)
    effective_from = models.DateTimeField()
    effective_until = models.DateTimeField(null=True, blank=True)
    eligibility_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.effective_until and self.effective_until < self.effective_from:
            raise ValidationError("Bonus end must be after its start.")

    @classmethod
    def applicable(cls, at):
        return cls.objects.filter(active=True, effective_from__lte=at).filter(
            Q(effective_until__isnull=True) | Q(effective_until__gte=at)
        ).order_by("-effective_from", "-created_at").first()


class EconomicSettlement(models.Model):
    collection = models.OneToOneField(CollectionRequest, on_delete=models.PROTECT, related_name="economic_settlement")
    category = models.ForeignKey(WasteCategory, on_delete=models.PROTECT)
    policy = models.ForeignKey(EconomicPolicy, on_delete=models.PROTECT)
    material_rate = models.ForeignKey(MaterialRate, on_delete=models.PROTECT)
    bonus = models.ForeignKey(CollectorBonus, on_delete=models.PROTECT, null=True, blank=True)
    material = models.CharField(max_length=150)
    unit = models.CharField(max_length=10)
    verified_quantity = models.DecimalField(max_digits=15, decimal_places=5)
    material_rate_value = models.DecimalField(max_digits=12, decimal_places=2)
    gross_value = models.DecimalField(max_digits=12, decimal_places=2)
    customer_percent = models.DecimalField(max_digits=5, decimal_places=2)
    collector_percent = models.DecimalField(max_digits=5, decimal_places=2)
    operations_percent = models.DecimalField(max_digits=5, decimal_places=2)
    customer_allocation = models.DecimalField(max_digits=12, decimal_places=2)
    customer_tokens = models.DecimalField(max_digits=12, decimal_places=2)
    collector_base_earning = models.DecimalField(max_digits=12, decimal_places=2)
    operations_allocation = models.DecimalField(max_digits=12, decimal_places=2)
    bonus_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_collector_earning = models.DecimalField(max_digits=12, decimal_places=2)
    settled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-settled_at"]


class CollectorPayout(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"

    collector = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="collector_payouts")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    currency = models.CharField(max_length=10, default="TZS")
    payout_method = models.CharField(max_length=20, default="mobile_money")
    provider_name = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    admin_notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="processed_collector_payouts")

    class Meta:
        ordering = ["-requested_at"]

    @property
    def masked_destination(self):
        if len(self.destination) <= 4:
            return "*" * len(self.destination)
        return "*" * (len(self.destination) - 4) + self.destination[-4:]

    def transition_to(self, new_status, admin_user, admin_notes=""):
        from django.db import transaction

        valid_transitions = {
            self.Status.PENDING: {self.Status.PROCESSING, self.Status.REJECTED},
            self.Status.PROCESSING: {self.Status.COMPLETED, self.Status.REJECTED},
        }
        with transaction.atomic():
            payout = type(self).objects.select_for_update().get(pk=self.pk)
            if new_status not in valid_transitions.get(payout.status, set()):
                raise ValidationError(f"Cannot move a {payout.get_status_display()} payout to {new_status}.")
            payout.status = new_status
            payout.admin_notes = admin_notes
            if new_status in {self.Status.COMPLETED, self.Status.REJECTED}:
                payout.processed_at = timezone.now()
                payout.processed_by = admin_user
            payout.save(update_fields=["status", "admin_notes", "processed_at", "processed_by"])
            if new_status == self.Status.REJECTED:
                wallet = CollectorWallet.objects.select_for_update().get(user=payout.collector)
                reference = f"collector-payout-refund-{payout.pk}"
                if not wallet.transactions.filter(reference=reference).exists():
                    CollectorWalletTransaction.objects.create(
                        collector_wallet=wallet,
                        transaction_type=CollectorWalletTransaction.TransactionType.REFUND,
                        amount=payout.amount,
                        description=f"Refund for rejected collector payout #{payout.pk}",
                        payout=payout,
                        reference=reference,
                    )
        self.refresh_from_db()
        return self
