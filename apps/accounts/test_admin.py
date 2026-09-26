from django.test import TestCase
from django.urls import reverse

from .models import User
from apps.wallet.models import Wallet


class OperationsAdminPageTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="operations_admin",
            email="operations@example.com",
            password="Strong-pass-123!",
        )
        self.client.force_login(self.admin_user)

    def test_registered_operations_changelists_load_and_accept_search(self):
        changelists = (
            "accounts_user", "accounts_collectorprofile", "waste_wastecategory", "waste_wastereport",
            "collections_collectionrequest", "wallet_wallet", "wallet_wallettransaction",
            "rewards_reward", "rewards_rewardredemption", "cashout_cashoutrate",
            "cashout_cashoutrequest", "marketplace_marketplacematerial", "marketplace_buyerrequest",
        )
        for model_name in changelists:
            with self.subTest(model=model_name):
                url = reverse(f"admin:{model_name}_changelist")
                response = self.client.get(url, {"q": "example"})
                self.assertEqual(response.status_code, 200)

    def test_users_with_wallets_cannot_be_deleted_but_can_be_deactivated(self):
        user = User.objects.create_user(username="ledger_user", password="Strong-pass-123!")
        wallet = Wallet.objects.get(user=user)
        response = self.client.post(
            reverse("admin:accounts_user_changelist"),
            {"action": "deactivate_users", "_selected_action": [str(user.pk)]},
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_users_can_be_anonymized_while_financial_data_is_preserved(self):
        user = User.objects.create_user(
            username="private_user", password="Strong-pass-123!",
            email="private@example.com", phone_number="0712345678",
        )
        wallet = Wallet.objects.get(user=user)
        response = self.client.post(
            reverse("admin:accounts_user_changelist"),
            {"action": "anonymize_users", "_selected_action": [str(user.pk)]},
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.username, f"deleted-user-{user.pk}")
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.email, "")
        self.assertTrue(Wallet.objects.filter(pk=wallet.pk, user=user).exists())
