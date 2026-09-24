from django.test import TestCase
from django.urls import reverse

from .models import User


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
