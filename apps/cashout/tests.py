from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.wallet.models import WalletTransaction

from .models import CashOutRate, CashOutRequest


class CashOutTestMixin:
    def create_rate(self, **overrides):
        values = {
            "tokens_per_money_unit": Decimal("100.00"),
            "money_amount": Decimal("1000.00"),
            "currency": "TZS",
            "active": True,
        }
        values.update(overrides)
        return CashOutRate.objects.create(**values)

    def fund_wallet(self, customer, amount="1500.00"):
        return WalletTransaction.objects.create(
            wallet=customer.wallet,
            transaction_type=WalletTransaction.TransactionType.COLLECTION_REWARD,
            amount=Decimal(amount),
            description="Test collection reward",
            reference=f"fund-{customer.username}",
        )

    def create_request(self, customer, **overrides):
        values = {
            "customer": customer,
            "token_amount": Decimal("1000.00"),
            "money_amount": Decimal("10000.00"),
            "currency": "TZS",
            "tokens_per_money_unit": Decimal("100.00"),
            "payout_method": CashOutRequest.PayoutMethod.MOBILE_MONEY,
            "provider_name": "M-Pesa",
            "phone_number": "0712345678",
            "status": CashOutRequest.Status.PENDING,
        }
        values.update(overrides)
        return CashOutRequest.objects.create(**values)


class CashOutAccessTests(CashOutTestMixin, TestCase):
    def setUp(self):
        self.rate = self.create_rate()
        self.customer = User.objects.create_user(username="cashout_customer", password="Strong-pass-123!", role=User.Role.CUSTOMER)
        self.collector = User.objects.create_user(username="cashout_collector", password="Strong-pass-123!", role=User.Role.COLLECTOR)

    def test_anonymous_user_cannot_access_cashout_pages(self):
        self.assertRedirects(self.client.get(reverse("cashout_create")), f"{reverse('login')}?next={reverse('cashout_create')}")
        self.assertRedirects(self.client.get(reverse("cashout_history")), f"{reverse('login')}?next={reverse('cashout_history')}")

    def test_customer_can_access_cashout_page(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("cashout_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cash-out")

    def test_collector_cannot_access_cashout_page(self):
        self.client.force_login(self.collector)
        self.assertRedirects(self.client.get(reverse("cashout_create")), reverse("dashboard"))

    def test_history_is_owned_by_logged_in_customer(self):
        other = User.objects.create_user(username="other_cashout", password="Strong-pass-123!", role=User.Role.CUSTOMER)
        self.create_request(other)
        self.client.force_login(self.customer)
        response = self.client.get(reverse("cashout_history"))
        self.assertNotContains(response, "other_cashout")
        self.assertNotContains(response, "0712345678")


class CashOutCreationTests(CashOutTestMixin, TestCase):
    def setUp(self):
        self.rate = self.create_rate()
        self.customer = User.objects.create_user(username="cashout_creator", password="Strong-pass-123!", role=User.Role.CUSTOMER)
        self.client.force_login(self.customer)
        self.fund_wallet(self.customer)

    def post(self, **data):
        values = {
            "token_amount": "1000.00",
            "payout_method": CashOutRequest.PayoutMethod.MOBILE_MONEY,
            "provider_name": "M-Pesa",
            "phone_number": "0712345678",
            "account_number": "",
        }
        values.update(data)
        return self.client.post(reverse("cashout_create"), values)

    def test_valid_mobile_money_cashout_deducts_tokens_and_stores_rate(self):
        response = self.post()
        self.assertRedirects(response, reverse("cashout_history"))
        request = CashOutRequest.objects.get()
        transaction = WalletTransaction.objects.get(transaction_type=WalletTransaction.TransactionType.CASHOUT)
        self.assertEqual(request.status, CashOutRequest.Status.PENDING)
        self.assertEqual(request.money_amount, Decimal("10000.00"))
        self.assertEqual(request.tokens_per_money_unit, Decimal("100.00"))
        self.assertEqual(request.currency, "TZS")
        self.assertEqual(transaction.amount, Decimal("-1000.00"))
        self.assertEqual(transaction.reference, f"cashout-{request.pk}")
        self.assertEqual(self.customer.wallet.balance, Decimal("500.00"))

    def test_valid_bank_cashout_uses_account_number(self):
        response = self.post(
            payout_method=CashOutRequest.PayoutMethod.BANK,
            provider_name="CRDB Bank",
            phone_number="",
            account_number="00123456789",
        )
        self.assertEqual(response.status_code, 302)
        request = CashOutRequest.objects.get()
        self.assertEqual(request.payout_method, CashOutRequest.PayoutMethod.BANK)
        self.assertEqual(request.account_number, "00123456789")
        self.assertEqual(request.phone_number, "")

    def test_rate_changes_do_not_change_existing_request(self):
        self.post()
        request = CashOutRequest.objects.get()
        self.rate.tokens_per_money_unit = Decimal("50.00")
        self.rate.money_amount = Decimal("1000.00")
        self.rate.save()
        request.refresh_from_db()
        self.assertEqual(request.money_amount, Decimal("10000.00"))
        self.assertEqual(request.tokens_per_money_unit, Decimal("100.00"))

    def test_client_money_amount_is_not_trusted(self):
        response = self.post(money_amount="1.00", token_amount="1000.00")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CashOutRequest.objects.get().money_amount, Decimal("10000.00"))

    def test_insufficient_balance_does_not_create_request_or_transaction(self):
        self.customer.wallet.transactions.all().delete()
        self.post()
        self.assertFalse(CashOutRequest.objects.exists())
        self.assertFalse(WalletTransaction.objects.filter(transaction_type=WalletTransaction.TransactionType.CASHOUT).exists())

    def test_zero_and_negative_token_amounts_are_rejected(self):
        for amount in ("0", "-1"):
            self.post(token_amount=amount)
            self.assertFalse(CashOutRequest.objects.exists())

    def test_destination_validation_depends_on_payout_method(self):
        self.post(phone_number="")
        self.assertFalse(CashOutRequest.objects.exists())
        self.post(payout_method=CashOutRequest.PayoutMethod.BANK, provider_name="NMB", phone_number="", account_number="")
        self.assertFalse(CashOutRequest.objects.exists())
        self.post(provider_name="   ")
        self.assertFalse(CashOutRequest.objects.exists())

    def test_atomic_failure_does_not_leave_request_or_deduction(self):
        with patch("apps.cashout.views.WalletTransaction.objects.create", side_effect=RuntimeError("ledger failure")):
            with self.assertRaises(RuntimeError):
                self.post()
        self.assertFalse(CashOutRequest.objects.exists())
        self.assertEqual(self.customer.wallet.balance, Decimal("1500.00"))


class CashOutWorkflowTests(CashOutTestMixin, TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="cashout_admin", email="admin@example.com", password="Strong-pass-123!")
        self.customer = User.objects.create_user(username="workflow_customer", password="Strong-pass-123!", role=User.Role.CUSTOMER)
        self.request = self.create_request(self.customer)
        self.cashout_transaction = WalletTransaction.objects.create(
            wallet=self.customer.wallet,
            transaction_type=WalletTransaction.TransactionType.CASHOUT,
            amount=Decimal("-1000.00"),
            description=f"Cash-out request #{self.request.pk}",
            reference=f"cashout-{self.request.pk}",
        )

    def test_pending_processing_completed_workflow(self):
        self.request.transition_to(CashOutRequest.Status.PROCESSING, self.admin)
        self.request.transition_to(CashOutRequest.Status.COMPLETED, self.admin, "Paid manually")
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, CashOutRequest.Status.COMPLETED)
        self.assertEqual(self.request.processed_by, self.admin)
        self.assertIsNotNone(self.request.processed_at)
        self.assertEqual(WalletTransaction.objects.filter(transaction_type=WalletTransaction.TransactionType.CASHOUT).count(), 1)

    def test_rejection_refunds_once_and_preserves_cashout(self):
        self.request.transition_to(CashOutRequest.Status.REJECTED, self.admin, "Invalid destination")
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, CashOutRequest.Status.REJECTED)
        refund = WalletTransaction.objects.get(transaction_type=WalletTransaction.TransactionType.ADJUSTMENT)
        self.assertEqual(refund.amount, Decimal("1000.00"))
        self.assertEqual(WalletTransaction.objects.filter(transaction_type=WalletTransaction.TransactionType.CASHOUT).count(), 1)
        with self.assertRaises(ValidationError):
            self.request.transition_to(CashOutRequest.Status.REJECTED, self.admin)
        self.assertEqual(WalletTransaction.objects.filter(transaction_type=WalletTransaction.TransactionType.ADJUSTMENT).count(), 1)

    def test_completed_request_cannot_be_processed_again(self):
        self.request.transition_to(CashOutRequest.Status.PROCESSING, self.admin)
        self.request.transition_to(CashOutRequest.Status.COMPLETED, self.admin)
        with self.assertRaises(ValidationError):
            self.request.transition_to(CashOutRequest.Status.PROCESSING, self.admin)

    def test_masked_destination_hides_sensitive_prefix(self):
        self.assertEqual(self.request.masked_destination, "******5678")