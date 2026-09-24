from decimal import Decimal

from io import BytesIO

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CollectorProfile, User
from apps.collections.models import CollectionRequest
from apps.waste.models import WasteCategory, WasteReport

from .models import Wallet, WalletTransaction


class WalletModelTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="customer_wallet",
            password="Strong-pass-123!",
            role=User.Role.CUSTOMER,
        )
        self.wallet = self.customer.wallet

    def test_new_wallet_balance_is_zero(self):
        self.assertEqual(self.wallet.balance, Decimal("0.00"))

    def test_positive_transaction_increases_balance(self):
        WalletTransaction.objects.create(
            wallet=self.wallet,
            transaction_type=WalletTransaction.TransactionType.COLLECTION_REWARD,
            amount=Decimal("100.00"),
            description="Collection reward",
            reference="reward-1",
        )
        self.assertEqual(self.wallet.balance, Decimal("100.00"))

    def test_negative_transaction_decreases_balance(self):
        WalletTransaction.objects.create(
            wallet=self.wallet,
            transaction_type=WalletTransaction.TransactionType.REWARD_REDEMPTION,
            amount=Decimal("-50.00"),
            description="Reward redemption",
            reference="reward-redemption-1",
        )
        self.assertEqual(self.wallet.balance, Decimal("-50.00"))

    def test_multiple_transactions_are_summed_correctly(self):
        WalletTransaction.objects.create(
            wallet=self.wallet,
            transaction_type=WalletTransaction.TransactionType.COLLECTION_REWARD,
            amount=Decimal("150.00"),
            description="Collection reward 1",
            reference="reward-1",
        )
        WalletTransaction.objects.create(
            wallet=self.wallet,
            transaction_type=WalletTransaction.TransactionType.COLLECTION_REWARD,
            amount=Decimal("75.50"),
            description="Collection reward 2",
            reference="reward-2",
        )
        WalletTransaction.objects.create(
            wallet=self.wallet,
            transaction_type=WalletTransaction.TransactionType.REWARD_REDEMPTION,
            amount=Decimal("-40.25"),
            description="Reward redemption",
            reference="redemption-1",
        )
        self.assertEqual(self.wallet.balance, Decimal("185.25"))

    def test_no_transactions_returns_zero(self):
        self.wallet.transactions.all().delete()
        self.assertEqual(self.wallet.balance, Decimal("0.00"))

    def test_customer_gets_wallet(self):
        self.assertIsNotNone(self.customer.wallet)
        self.assertEqual(self.customer.wallet.user, self.customer)

    def test_duplicate_wallet_cannot_exist(self):
        with self.assertRaises(IntegrityError):
            Wallet.objects.create(user=self.customer)

    def test_collector_does_not_receive_customer_wallet(self):
        collector = User.objects.create_user(
            username="collector_wallet",
            password="Strong-pass-123!",
            role=User.Role.COLLECTOR,
        )
        self.assertFalse(Wallet.objects.filter(user=collector).exists())

    def test_no_buyer_user_role_is_defined(self):
        self.assertNotIn("buyer", User.Role.values)

    def test_token_rate_cannot_be_negative(self):
        category = WasteCategory(name="Paper", active=True, token_rate_per_kg=Decimal("-1.00"))
        with self.assertRaises(Exception):
            category.full_clean()

    def test_wallet_transactions_are_not_created_via_public_post(self):
        initial_count = WalletTransaction.objects.count()
        response = self.client.post(reverse("wallet"), {"amount": "25.00"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WalletTransaction.objects.count(), initial_count)


class WalletAccessTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="customer_access",
            password="Strong-pass-123!",
            role=User.Role.CUSTOMER,
        )
        self.collector = User.objects.create_user(
            username="collector_access",
            password="Strong-pass-123!",
            role=User.Role.COLLECTOR,
        )

    def test_customer_can_view_own_wallet(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("wallet"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wallet")

    def test_anonymous_user_cannot_access_wallet(self):
        response = self.client.get(reverse("wallet"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('wallet')}")

    def test_collector_cannot_access_customer_wallet(self):
        self.client.force_login(self.collector)
        response = self.client.get(reverse("wallet"))
        self.assertRedirects(response, reverse("dashboard"))


class CollectionRewardTests(TestCase):
    def setUp(self):
        self.category = WasteCategory.objects.create(
            name="Plastic",
            active=True,
            token_rate_per_kg=Decimal("100.00"),
        )
        self.customer = User.objects.create_user(
            username="reward_customer",
            password="Strong-pass-123!",
            role=User.Role.CUSTOMER,
        )
        self.collector = User.objects.create_user(
            username="reward_collector",
            password="Strong-pass-123!",
            role=User.Role.COLLECTOR,
        )
        CollectorProfile.objects.create(
            user=self.collector,
            verification_status=CollectorProfile.VerificationStatus.APPROVED,
            identification_reference="COL-500",
            address="Stone Town",
        )
        self.report = WasteReport.objects.create(
            customer=self.customer,
            category=self.category,
            description="Plastic bottles",
            estimated_weight=Decimal("3.50"),
            weight_unit=WasteReport.WeightUnit.KILOGRAMS,
            latitude=Decimal("-6.1659"),
            longitude=Decimal("39.2026"),
            location_accuracy=Decimal("15.00"),
            status=WasteReport.Status.SUBMITTED,
        )
        self.collection = CollectionRequest.objects.create(waste_report=self.report)

    def test_completion_creates_one_reward_transaction(self):
        self.collection.collector = self.collector
        self.collection.status = CollectionRequest.Status.ACCEPTED
        self.collection.save()
        self.client.force_login(self.collector)
        image = Image.new("RGB", (10, 10), color="green")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        photo = SimpleUploadedFile("proof.png", buffer.getvalue(), content_type="image/png")
        response = self.client.post(
            reverse("collection_complete", args=[self.collection.id]),
            {
                "actual_weight": "2.50",
                "weight_unit": WasteReport.WeightUnit.KILOGRAMS,
                "proof_photo": photo,
                "notes": "Collected successfully.",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.collection.reward_transaction.amount, Decimal("250.00"))
        self.assertEqual(self.collection.reward_transaction.wallet, self.customer.wallet)
        self.assertEqual(self.customer.wallet.balance, Decimal("250.00"))
        self.assertEqual(self.collection.reward_transaction.transaction_type, WalletTransaction.TransactionType.COLLECTION_REWARD)

    def test_second_completion_attempt_does_not_create_another_reward(self):
        self.collection.collector = self.collector
        self.collection.status = CollectionRequest.Status.ACCEPTED
        self.collection.save()
        self.client.force_login(self.collector)
        image = Image.new("RGB", (10, 10), color="green")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        photo = SimpleUploadedFile("proof.png", buffer.getvalue(), content_type="image/png")

        self.client.post(
            reverse("collection_complete", args=[self.collection.id]),
            {
                "actual_weight": "2.50",
                "weight_unit": WasteReport.WeightUnit.KILOGRAMS,
                "proof_photo": photo,
                "notes": "Collected successfully.",
            },
        )
        before_count = WalletTransaction.objects.filter(wallet=self.customer.wallet).count()
        response = self.client.post(
            reverse("collection_complete", args=[self.collection.id]),
            {
                "actual_weight": "1.00",
                "weight_unit": WasteReport.WeightUnit.KILOGRAMS,
                "proof_photo": photo,
                "notes": "Repeat attempt.",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WalletTransaction.objects.filter(wallet=self.customer.wallet).count(), before_count)

    def test_gram_weight_is_converted_correctly_in_reward_calculation(self):
        self.collection.collector = self.collector
        self.collection.status = CollectionRequest.Status.ACCEPTED
        self.collection.actual_weight = Decimal("2500")
        self.collection.weight_unit = WasteReport.WeightUnit.GRAMS
        self.collection.save()
        self.client.force_login(self.collector)
        image = Image.new("RGB", (10, 10), color="green")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        photo = SimpleUploadedFile("proof.png", buffer.getvalue(), content_type="image/png")

        self.client.post(
            reverse("collection_complete", args=[self.collection.id]),
            {
                "actual_weight": "2500",
                "weight_unit": WasteReport.WeightUnit.GRAMS,
                "proof_photo": photo,
                "notes": "Collected successfully.",
            },
        )

        self.assertEqual(self.customer.wallet.balance, Decimal("250.00"))

    def test_reward_creation_failure_rolls_back_collection_completion(self):
        self.collection.collector = self.collector
        self.collection.status = CollectionRequest.Status.ACCEPTED
        self.collection.save()
        self.client.force_login(self.collector)
        image = Image.new("RGB", (10, 10), color="green")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        photo = SimpleUploadedFile("proof.png", buffer.getvalue(), content_type="image/png")

        with self.assertRaises(Exception):
            with self.settings(DEBUG=True):
                from unittest.mock import patch

                with patch("apps.wallet.models.WalletTransaction.objects.create", side_effect=Exception("boom")):
                    self.client.post(
                        reverse("collection_complete", args=[self.collection.id]),
                        {
                            "actual_weight": "2.50",
                            "weight_unit": WasteReport.WeightUnit.KILOGRAMS,
                            "proof_photo": photo,
                            "notes": "Collected successfully.",
                        },
                    )

        self.collection.refresh_from_db()
        self.assertEqual(self.collection.status, CollectionRequest.Status.ACCEPTED)
        self.assertFalse(WalletTransaction.objects.filter(collection=self.collection).exists())
