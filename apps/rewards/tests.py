from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.wallet.models import WalletTransaction

from .models import Reward, RewardRedemption


class RewardTestMixin:
    def create_image(self):
        image = Image.new("RGB", (20, 20), color="green")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return SimpleUploadedFile("reward.png", buffer.getvalue(), content_type="image/png")

    def create_reward(self, **overrides):
        values = {
            "name": "Reusable Shopping Bag",
            "description": "A durable bag for everyday shopping.",
            "token_cost": Decimal("750.00"),
            "inventory": 2,
            "active": True,
        }
        values.update(overrides)
        return Reward.objects.create(**values)


class RewardAccessTests(RewardTestMixin, TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username="reward_customer", password="Strong-pass-123!", role=User.Role.CUSTOMER)
        self.collector = User.objects.create_user(username="reward_collector", password="Strong-pass-123!", role=User.Role.COLLECTOR)
        self.active_reward = self.create_reward()
        self.inactive_reward = self.create_reward(name="Hidden Reward", active=False)

    def test_anonymous_user_cannot_access_rewards_pages(self):
        self.assertRedirects(self.client.get(reverse("reward_list")), f"{reverse('login')}?next={reverse('reward_list')}")
        self.assertRedirects(self.client.get(reverse("redemption_history")), f"{reverse('login')}?next={reverse('redemption_history')}")

    def test_collector_cannot_access_rewards_pages_or_redeem(self):
        self.client.force_login(self.collector)
        self.assertRedirects(self.client.get(reverse("reward_list")), reverse("dashboard"))
        self.assertRedirects(self.client.post(reverse("redeem_reward", args=[self.active_reward.id])), reverse("dashboard"))

    def test_customer_sees_only_active_rewards(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("reward_list"))
        self.assertContains(response, self.active_reward.name)
        self.assertNotContains(response, self.inactive_reward.name)

    def test_inactive_reward_is_not_redeemable_or_viewable(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("reward_detail", args=[self.inactive_reward.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("redeem_reward", args=[self.inactive_reward.id])).status_code, 404)


class RewardDataTests(RewardTestMixin, TestCase):
    def test_reward_image_and_description_are_stored(self):
        reward = self.create_reward(image=self.create_image())
        self.assertIn("rewards/", reward.image.name)
        self.assertEqual(reward.description, "A durable bag for everyday shopping.")

    def test_token_cost_must_be_at_least_one_cent(self):
        reward = Reward(name="Invalid", description="Invalid", token_cost=Decimal("0.00"), inventory=0)
        with self.assertRaises(ValidationError):
            reward.full_clean()

    def test_inventory_cannot_be_negative(self):
        reward = Reward(name="Invalid", description="Invalid", token_cost=Decimal("1.00"), inventory=-1)
        with self.assertRaises(ValidationError):
            reward.full_clean()


class RedemptionTests(RewardTestMixin, TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username="redeemer", password="Strong-pass-123!", role=User.Role.CUSTOMER)
        self.client.force_login(self.customer)
        self.reward = self.create_reward()
        WalletTransaction.objects.create(
            wallet=self.customer.wallet,
            transaction_type=WalletTransaction.TransactionType.COLLECTION_REWARD,
            amount=Decimal("1500.00"),
            description="Test token award",
            reference="test-award",
        )

    def redeem_url(self):
        return reverse("redeem_reward", args=[self.reward.id])

    def test_successful_redemption_creates_history_and_negative_ledger_entry(self):
        response = self.client.post(self.redeem_url())
        self.assertRedirects(response, reverse("reward_detail", args=[self.reward.id]))
        self.reward.refresh_from_db()
        redemption = RewardRedemption.objects.get()
        transaction = WalletTransaction.objects.get(transaction_type=WalletTransaction.TransactionType.REWARD_REDEMPTION)
        self.assertEqual(redemption.customer, self.customer)
        self.assertEqual(redemption.reward, self.reward)
        self.assertEqual(redemption.token_amount, Decimal("750.00"))
        self.assertEqual(redemption.status, RewardRedemption.Status.COMPLETED)
        self.assertEqual(transaction.amount, Decimal("-750.00"))
        self.assertEqual(transaction.reference, f"redemption-{redemption.pk}")
        self.assertEqual(self.customer.wallet.balance, Decimal("750.00"))
        self.assertEqual(self.reward.inventory, 1)

    def test_browser_token_amount_cannot_override_reward_price(self):
        response = self.client.post(self.redeem_url(), {"token_amount": "1.00"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RewardRedemption.objects.get().token_amount, Decimal("750.00"))
        self.assertEqual(self.customer.wallet.balance, Decimal("750.00"))

    def test_get_does_not_redeem(self):
        response = self.client.get(self.redeem_url())
        self.assertRedirects(response, reverse("reward_detail", args=[self.reward.id]))
        self.assertFalse(RewardRedemption.objects.exists())
        self.assertEqual(self.reward.inventory, 2)

    def test_csrf_is_required_for_redemption(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.customer)
        response = csrf_client.post(self.redeem_url())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(RewardRedemption.objects.exists())

    def test_insufficient_balance_rolls_back_everything(self):
        self.customer.wallet.transactions.all().delete()
        self.client.post(self.redeem_url())
        self.assertFalse(RewardRedemption.objects.exists())
        self.assertFalse(WalletTransaction.objects.exists())
        self.reward.refresh_from_db()
        self.assertEqual(self.reward.inventory, 2)

    def test_out_of_stock_cannot_be_redeemed(self):
        self.reward.inventory = 0
        self.reward.save(update_fields=["inventory", "updated_at"])
        self.client.post(self.redeem_url())
        self.assertFalse(RewardRedemption.objects.exists())
        self.assertEqual(self.customer.wallet.balance, Decimal("1500.00"))

    def test_atomic_rollback_removes_redemption_and_preserves_inventory(self):
        with patch("apps.rewards.views.WalletTransaction.objects.create", side_effect=RuntimeError("ledger failure")):
            with self.assertRaises(RuntimeError):
                self.client.post(self.redeem_url())
        self.assertFalse(RewardRedemption.objects.exists())
        self.assertEqual(self.customer.wallet.balance, Decimal("1500.00"))
        self.reward.refresh_from_db()
        self.assertEqual(self.reward.inventory, 2)


class RedemptionOwnershipTests(RewardTestMixin, TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username="history_owner", password="Strong-pass-123!", role=User.Role.CUSTOMER)
        self.other_customer = User.objects.create_user(username="other_customer", password="Strong-pass-123!", role=User.Role.CUSTOMER)
        self.reward = self.create_reward()
        RewardRedemption.objects.create(
            customer=self.other_customer,
            reward=self.reward,
            token_amount=self.reward.token_cost,
            status=RewardRedemption.Status.COMPLETED,
        )

    def test_history_only_contains_logged_in_customers_records(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("redemption_history"))
        self.assertNotContains(response, self.other_customer.username)
        self.assertNotContains(response, self.reward.name)