from decimal import Decimal
from io import BytesIO

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User
from apps.collections.models import CollectionRequest
from apps.marketplace.models import MarketplaceMaterial
from apps.waste.models import WasteCategory, WasteReport
from apps.wallet.models import WalletTransaction

from .models import CollectorBonus, CollectorWalletTransaction, EconomicPolicy, EconomicSettlement, MaterialRate
from .services import request_collector_payout, settle_collection


class EconomicsTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.customer = User.objects.create_user(username="economic_customer", password="Strong-pass-123!", role=User.Role.CUSTOMER)
        self.collector = User.objects.create_user(username="economic_collector", password="Strong-pass-123!", role=User.Role.COLLECTOR)
        self.category = WasteCategory.objects.create(name="PET", reward_unit=WasteCategory.RewardUnit.KILOGRAM, token_rate=Decimal("100.00"))
        self.policy = EconomicPolicy.objects.create(
            name="Pilot 30/30/40", category=self.category, customer_percent=Decimal("30.00"),
            collector_percent=Decimal("30.00"), operations_percent=Decimal("40.00"), effective_from=now,
        )
        self.rate = MaterialRate.objects.create(category=self.category, rate_per_unit=Decimal("100.00"), effective_from=now)
        self.report = WasteReport.objects.create(
            customer=self.customer, category=self.category, description="PET bottles", estimated_weight=Decimal("10.00"),
            weight_unit=WasteReport.WeightUnit.KILOGRAMS, latitude=Decimal("-6.165900"), longitude=Decimal("39.202600"),
            location_accuracy=Decimal("10.00"), status=WasteReport.Status.PENDING_COLLECTION,
        )
        self.collection = CollectionRequest.objects.create(
            waste_report=self.report, collector=self.collector, status=CollectionRequest.Status.ACCEPTED,
            actual_weight=Decimal("10.00"), weight_unit=WasteReport.WeightUnit.KILOGRAMS,
        )

    def complete(self):
        image = Image.new("RGB", (10, 10), color="green")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        self.collection.proof_photo = SimpleUploadedFile("proof.png", buffer.getvalue(), content_type="image/png")
        self.collection.save(update_fields=["proof_photo"])
        return settle_collection(self.collection)

    def test_pilot_settlement_partitions_and_snapshots(self):
        CollectorBonus.objects.create(name="Pilot bonus", amount=Decimal("100.00"), effective_from=timezone.now())
        result = self.complete()
        settlement = result.settlement
        self.assertEqual(settlement.gross_value, Decimal("1000.00"))
        self.assertEqual(settlement.customer_allocation, Decimal("300.00"))
        self.assertEqual(settlement.customer_tokens, Decimal("300.00"))
        self.assertEqual(settlement.collector_base_earning, Decimal("300.00"))
        self.assertEqual(settlement.operations_allocation, Decimal("400.00"))
        self.assertEqual(settlement.total_collector_earning, Decimal("400.00"))
        self.assertEqual(result.collector_transaction.collector_wallet.balance, Decimal("400.00"))
        self.assertTrue(MarketplaceMaterial.objects.filter(source_collection=self.collection).exists())

    def test_policy_percentages_must_total_100(self):
        policy = EconomicPolicy(
            name="Invalid", category=self.category, customer_percent=Decimal("30.00"),
            collector_percent=Decimal("30.00"), operations_percent=Decimal("30.00"), effective_from=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            policy.full_clean()

    def test_duplicate_settlement_is_rejected(self):
        self.complete()
        with self.assertRaises(ValidationError):
            settle_collection(self.collection)
        self.assertEqual(EconomicSettlement.objects.filter(collection=self.collection).count(), 1)

    def test_snapshot_does_not_change_when_configuration_changes(self):
        result = self.complete()
        self.policy.customer_percent = Decimal("25.00")
        self.policy.collector_percent = Decimal("35.00")
        self.policy.operations_percent = Decimal("40.00")
        self.policy.save()
        self.rate.rate_per_unit = Decimal("200.00")
        self.rate.save()
        result.settlement.refresh_from_db()
        self.assertEqual(result.settlement.gross_value, Decimal("1000.00"))
        self.assertEqual(result.settlement.customer_tokens, Decimal("300.00"))

    def test_atomic_failure_rolls_back_all_settlement_records(self):
        self.rate.delete()
        with self.assertRaises(ValidationError):
            settle_collection(self.collection)
        self.assertFalse(EconomicSettlement.objects.exists())
        self.assertFalse(WalletTransaction.objects.filter(collection=self.collection).exists())
        self.assertFalse(MarketplaceMaterial.objects.filter(source_collection=self.collection).exists())

    def test_collector_payout_threshold_and_partial_balance(self):
        self.complete()
        collector_wallet = self.collector.collector_wallet
        CollectorWalletTransaction.objects.create(
            collector_wallet=collector_wallet,
            transaction_type=CollectorWalletTransaction.TransactionType.ADJUSTMENT,
            amount=Decimal("15000.00"),
            description="Test funding adjustment",
            reference="test-collector-funding",
        )
        with self.assertRaises(ValidationError):
            request_collector_payout(collector=self.collector, amount=Decimal("9999.99"), payout_method="mobile_money", provider_name="M-Pesa", destination="0712345678")
        payout = request_collector_payout(collector=self.collector, amount=Decimal("10000.00"), payout_method="mobile_money", provider_name="M-Pesa", destination="0712345678")
        self.assertEqual(payout.amount, Decimal("10000.00"))
        self.assertEqual(payout.collector.collector_wallet.balance, Decimal("5300.00"))
