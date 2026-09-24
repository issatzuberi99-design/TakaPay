from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CollectorProfile, User
from apps.cashout.models import CashOutRequest
from apps.collections.models import CollectionRequest
from apps.marketplace.models import BuyerRequest, MarketplaceMaterial
from apps.rewards.models import Reward, RewardRedemption
from apps.wallet.models import Wallet, WalletTransaction
from apps.waste.models import WasteCategory, WasteReport


class AdminAnalyticsDashboardTests(TestCase):
    def setUp(self):
        self.url = reverse("admin_analytics_dashboard")
        self.staff = User.objects.create_user(
            username="analytics_staff", email="staff@example.com", password="Strong-pass-123!",
            role=User.Role.CUSTOMER, is_staff=True,
        )
        self.customer = User.objects.create_user(
            username="analytics_customer", password="Strong-pass-123!", role=User.Role.CUSTOMER,
        )
        self.collector = User.objects.create_user(
            username="analytics_collector", password="Strong-pass-123!", role=User.Role.COLLECTOR,
        )
        self.admin = User.objects.create_superuser(
            username="analytics_admin", email="admin@example.com", password="Strong-pass-123!",
        )

    def test_anonymous_customer_and_collector_are_denied(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

        for user in (self.customer, self.collector):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_staff_and_custom_admin_users_can_view_dashboard(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 200)

        nonstaff_admin = User.objects.create_user(
            username="role_admin", password="Strong-pass-123!", role=User.Role.ADMIN,
        )
        self.client.force_login(nonstaff_admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_dashboard_has_kpis_and_builtin_admin_remains_available(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for heading in (
            "Total waste reports", "Estimated waste", "Collected actual waste", "Approved collectors",
            "Tokens issued", "Tokens redeemed", "Pending cash-outs", "Active rewards",
            "Active marketplace materials", "Pending buyer requests", "Waste reports over time",
        ):
            with self.subTest(heading=heading):
                self.assertContains(response, heading)

        admin_index = self.client.get(reverse("admin:index"))
        self.assertEqual(admin_index.status_code, 200)
        self.assertContains(admin_index, "Open TakaPay Analytics Dashboard")

    def test_empty_dashboard_displays_clean_empty_states(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No waste reports yet.")
        self.assertContains(response, "No marketplace requests yet.")
        self.assertContains(response, "No operational activity yet.")
        self.assertContains(response, "0.00 kg")

    def test_waste_totals_category_aggregation_and_daily_period_filter(self):
        category = WasteCategory.objects.create(name="Plastic", active=True)
        old_category = WasteCategory.objects.create(name="Old glass", active=False)
        recent = WasteReport.objects.create(
            customer=self.customer, category=category, description="Recent bottles",
            estimated_weight=Decimal("2.00"), weight_unit=WasteReport.WeightUnit.KILOGRAMS,
            latitude=Decimal("-6.100000"), longitude=Decimal("39.200000"),
            location_accuracy=Decimal("5.00"), status=WasteReport.Status.VERIFIED,
        )
        gram_report = WasteReport.objects.create(
            customer=self.customer, category=category, description="Recent small glass",
            estimated_weight=Decimal("500.00"), weight_unit=WasteReport.WeightUnit.GRAMS,
            latitude=Decimal("-6.100000"), longitude=Decimal("39.200000"),
            location_accuracy=Decimal("5.00"), status=WasteReport.Status.SUBMITTED,
        )
        old_report = WasteReport.objects.create(
            customer=self.customer, category=old_category, description="Older item",
            estimated_weight=Decimal("8.00"), weight_unit=WasteReport.WeightUnit.KILOGRAMS,
            latitude=Decimal("-6.100000"), longitude=Decimal("39.200000"),
            location_accuracy=Decimal("5.00"),
        )
        old_time = timezone.now() - timedelta(days=50)
        WasteReport.objects.filter(pk=old_report.pk).update(created_at=old_time)

        completed = CollectionRequest.objects.create(
            waste_report=recent, status=CollectionRequest.Status.COMPLETED,
            actual_weight=Decimal("1.25"), weight_unit=WasteReport.WeightUnit.KILOGRAMS,
            completed_at=timezone.now(),
        )
        CollectionRequest.objects.create(
            waste_report=gram_report, status=CollectionRequest.Status.COMPLETED,
            actual_weight=Decimal("750.00"), weight_unit=WasteReport.WeightUnit.GRAMS,
            completed_at=timezone.now(),
        )

        self.client.force_login(self.admin)
        response = self.client.get(self.url, {"period": "7"})
        context = response.context
        self.assertEqual(context["total_waste_reports"], 2)
        self.assertEqual(context["estimated_waste_kg"], Decimal("2.5000"))
        self.assertEqual(context["verified_waste_kg"], Decimal("2.0000"))
        self.assertEqual(context["collected_waste_kg"], Decimal("2.0000"))
        self.assertEqual(context["completed_collections"], 2)
        self.assertEqual(len(context["daily_activity"]), 7)
        category_row = next(row for row in context["category_activity"] if row.name == "Plastic")
        self.assertEqual(category_row.report_count, 2)
        self.assertEqual(category_row.estimated_kg, Decimal("2.5000"))
        self.assertEqual(category_row.collected_kg, Decimal("2.0000"))

        all_time = self.client.get(self.url, {"period": "all"})
        self.assertEqual(all_time.context["total_waste_reports"], 3)
        self.assertEqual(all_time.context["estimated_waste_kg"], Decimal("10.5000"))

    def test_collection_counts_and_approved_collector_count(self):
        category = WasteCategory.objects.create(name="Cardboard", active=True)
        for idx, status in enumerate(CollectionRequest.Status.values):
            report = WasteReport.objects.create(
                customer=self.customer, category=category, description=f"Report {idx}",
                estimated_weight=Decimal("1.00"), latitude=Decimal("-6.100000"),
                longitude=Decimal("39.200000"), location_accuracy=Decimal("5.00"),
            )
            CollectionRequest.objects.create(waste_report=report, status=status)
        CollectorProfile.objects.create(
            user=self.collector, verification_status=CollectorProfile.VerificationStatus.APPROVED,
            identification_reference="COL-ANALYTICS", address="Zanzibar",
        )

        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.context["collection_counts"], {status: 1 for status in CollectionRequest.Status.values})
        self.assertEqual(response.context["approved_collectors"], 1)
        self.assertEqual(response.context["collection_completion_rate"], Decimal("25.0"))

    def test_token_totals_come_from_wallet_ledger(self):
        wallet = self.customer.wallet
        entries = (
            (WalletTransaction.TransactionType.COLLECTION_REWARD, Decimal("300.00")),
            (WalletTransaction.TransactionType.REWARD_REDEMPTION, Decimal("-40.00")),
            (WalletTransaction.TransactionType.CASHOUT, Decimal("-50.00")),
            (WalletTransaction.TransactionType.ADJUSTMENT, Decimal("5.00")),
        )
        for transaction_type, amount in entries:
            WalletTransaction.objects.create(
                wallet=wallet, transaction_type=transaction_type, amount=amount,
                description="Analytics test entry",
            )

        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.context["tokens_issued"], Decimal("300.0000"))
        self.assertEqual(response.context["tokens_redeemed"], Decimal("40.0000"))
        self.assertEqual(response.context["tokens_requested_for_cashout"], Decimal("50.0000"))
        self.assertEqual(response.context["token_adjustments"], Decimal("5.0000"))

    def test_cashout_reward_and_marketplace_counts_and_private_data(self):
        reward = Reward.objects.create(name="Reusable bag", description="Bag", token_cost=Decimal("25.00"), inventory=4)
        Reward.objects.create(name="Inactive reward", description="Old", token_cost=Decimal("10.00"), active=False)
        for status in RewardRedemption.Status.values:
            RewardRedemption.objects.create(
                customer=self.customer, reward=reward, token_amount=Decimal("25.00"), status=status,
            )

        cashout_statuses = list(CashOutRequest.Status.values)
        for idx, status in enumerate(cashout_statuses):
            CashOutRequest.objects.create(
                customer=self.customer, token_amount=Decimal("10.00"), money_amount=Decimal("100.00"),
                currency="TZS", tokens_per_money_unit=Decimal("100.00"),
                payout_method=CashOutRequest.PayoutMethod.BANK, provider_name="Test Bank",
                account_number=f"PRIVATE-ACCOUNT-{idx}", status=status,
            )

        category = WasteCategory.objects.create(name="PET plastic", active=True)
        material = MarketplaceMaterial.objects.create(
            name="Recycled PET", description="Clean PET", category=category,
            available_quantity=Decimal("12.50"), unit=MarketplaceMaterial.Unit.KILOGRAM, active=True,
        )
        MarketplaceMaterial.objects.create(
            name="Aluminum parts", description="Parts", category=category,
            available_quantity=Decimal("3.00"), unit=MarketplaceMaterial.Unit.PIECE, active=True,
        )
        MarketplaceMaterial.objects.create(
            name="Inactive stock", description="Hidden", available_quantity=Decimal("99.00"),
            unit=MarketplaceMaterial.Unit.KILOGRAM, active=False,
        )
        buyer_statuses = list(BuyerRequest.Status.values)
        for status in buyer_statuses:
            BuyerRequest.objects.create(
                buyer_name="PRIVATE BUYER NAME", company_name="PRIVATE COMPANY",
                phone_number="PRIVATE BUYER PHONE", email="private-buyer@example.com",
                location="PRIVATE BUYER LOCATION", material=material, material_name=material.name,
                requested_quantity=Decimal("1.00"), unit=material.unit, status=status,
            )

        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        data = response.context
        self.assertEqual(data["cashout_counts"], {status: 1 for status in cashout_statuses})
        self.assertEqual(data["pending_cashouts"], 1)
        self.assertEqual(data["active_rewards"], 1)
        self.assertEqual(data["inactive_rewards"], 1)
        self.assertEqual(data["total_redemptions"], len(RewardRedemption.Status.values))
        self.assertEqual(data["active_materials"], 2)
        self.assertEqual(data["available_materials"], 2)
        self.assertEqual(
            {row["unit"]: row["quantity"] for row in data["marketplace_inventory"]},
            {MarketplaceMaterial.Unit.KILOGRAM: Decimal("12.5000"), MarketplaceMaterial.Unit.PIECE: Decimal("3.0000")},
        )
        self.assertEqual(data["buyer_counts"], {status: 1 for status in buyer_statuses})
        for sensitive_value in (
            "PRIVATE BUYER NAME", "PRIVATE COMPANY", "PRIVATE BUYER PHONE", "private-buyer@example.com",
            "PRIVATE BUYER LOCATION", "PRIVATE-ACCOUNT-0", "PRIVATE-ACCOUNT-4",
        ):
            self.assertNotContains(response, sensitive_value)

    def test_invalid_period_falls_back_and_empty_daily_series_is_filled(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {"period": "unexpected"})
        self.assertEqual(response.context["period"], "30")
        self.assertEqual(len(response.context["daily_activity"]), 30)
        self.assertTrue(all(row["report_count"] == 0 for row in response.context["daily_activity"]))
