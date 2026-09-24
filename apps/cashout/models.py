from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from apps.wallet.models import Wallet, WalletTransaction


class CashOutRate(models.Model):
    tokens_per_money_unit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    money_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=10, default="TZS")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-active", "-created_at"]

    def __str__(self):
        return f"{self.tokens_per_money_unit} tokens = {self.money_amount} {self.currency}"


class CashOutRequest(models.Model):
    class PayoutMethod(models.TextChoices):
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        BANK = "bank", "Bank"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cashout_requests",
        db_index=True,
    )
    token_amount = models.DecimalField(max_digits=12, decimal_places=2)
    money_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="TZS")
    tokens_per_money_unit = models.DecimalField(max_digits=12, decimal_places=2)
    payout_method = models.CharField(max_length=20, choices=PayoutMethod.choices)
    provider_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=30, blank=True)
    account_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    admin_notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_cashout_requests",
    )

    class Meta:
        ordering = ["-requested_at"]

    def clean(self):
        errors = {}
        if self.token_amount is not None and self.token_amount <= 0:
            errors["token_amount"] = "Token amount must be greater than zero."
        if not self.provider_name or not self.provider_name.strip():
            errors["provider_name"] = "Provider name is required."
        if self.payout_method == self.PayoutMethod.MOBILE_MONEY:
            if not self.phone_number or not self.phone_number.strip():
                errors["phone_number"] = "Phone number is required for mobile money."
            if self.account_number:
                errors["account_number"] = "Bank account number is not used for mobile money."
        elif self.payout_method == self.PayoutMethod.BANK:
            if not self.account_number or not self.account_number.strip():
                errors["account_number"] = "Account number is required for bank payouts."
            if self.phone_number:
                errors["phone_number"] = "Phone number is not used for bank payouts."
        if errors:
            raise ValidationError(errors)

    def transition_to(self, new_status, admin_user, admin_notes=""):
        valid_transitions = {
            self.Status.PENDING: {self.Status.PROCESSING, self.Status.REJECTED},
            self.Status.PROCESSING: {self.Status.COMPLETED, self.Status.REJECTED},
        }
        with transaction.atomic():
            request = type(self).objects.select_for_update().get(pk=self.pk)
            if new_status not in valid_transitions.get(request.status, set()):
                raise ValidationError(f"Cannot move a {request.get_status_display()} request to {new_status}.")
            request.status = new_status
            request.admin_notes = admin_notes
            if new_status in {self.Status.COMPLETED, self.Status.REJECTED}:
                request.processed_at = timezone.now()
                request.processed_by = admin_user
            request.save(update_fields=["status", "admin_notes", "processed_at", "processed_by"])
            if new_status == self.Status.REJECTED:
                refund_reference = f"cashout-refund-{request.pk}"
                if not WalletTransaction.objects.filter(reference=refund_reference).exists():
                    wallet = Wallet.objects.select_for_update().get(user=request.customer)
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type=WalletTransaction.TransactionType.ADJUSTMENT,
                        amount=request.token_amount,
                        description=f"Refund for rejected cash-out #{request.pk}",
                        reference=refund_reference,
                    )
        self.refresh_from_db()
        return self

    def __str__(self):
        return f"Cash-out #{self.pk} for {self.customer.username}"

    @property
    def masked_destination(self):
        value = self.phone_number or self.account_number
        if len(value) <= 4:
            return "*" * len(value)
        return "*" * (len(value) - 4) + value[-4:]

    @staticmethod
    def calculate_money_amount(token_amount, rate):
        return (token_amount / rate.tokens_per_money_unit * rate.money_amount).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )