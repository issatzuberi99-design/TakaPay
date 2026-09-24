from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CollectorProfile, User
from apps.collections.models import CollectionRequest
from apps.marketplace.models import MarketplaceMaterial
from apps.waste.models import WasteCategory, WasteReport


class AdminOperationsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="ops_admin", password="Strong-pass-123!", role=User.Role.ADMIN,
        )
        self.customer = User.objects.create_user(username="ops_customer", password="Strong-pass-123!")
        self.collector = User.objects.create_user(
            username="ops_collector", password="Strong-pass-123!", role=User.Role.COLLECTOR,
        )
        self.category = WasteCategory.objects.create(
            name="Plastic", active=True, token_rate=Decimal("2.75"),
        )
        self.client.force_login(self.admin)

    def test_admin_can_view_rates_and_save_decimal_rate(self):
        url = reverse("admin_token_rates")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reward Unit")
        self.assertContains(response, "Tokens per selected unit")
        self.assertContains(response, "Plastic")
        response = self.client.post(url, {
            "rates-TOTAL_FORMS": "1", "rates-INITIAL_FORMS": "1",
            "rates-MIN_NUM_FORMS": "0", "rates-MAX_NUM_FORMS": "1000",
            "rates-0-id": str(self.category.pk), "rates-0-reward_unit": "piece", "rates-0-token_rate": "12.35", "rates-0-active": "",
        })
        self.assertRedirects(response, url)
        self.category.refresh_from_db()
        self.assertEqual(self.category.token_rate, Decimal("12.35"))
        self.assertEqual(self.category.reward_unit, WasteCategory.RewardUnit.PIECE)
        self.assertFalse(self.category.active)

    def test_negative_rate_is_rejected(self):
        response = self.client.post(reverse("admin_token_rates"), {
            "rates-TOTAL_FORMS": "1", "rates-INITIAL_FORMS": "1",
            "rates-MIN_NUM_FORMS": "0", "rates-MAX_NUM_FORMS": "1000",
            "rates-0-id": str(self.category.pk), "rates-0-reward_unit": "kg", "rates-0-token_rate": "-1.00", "rates-0-active": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.category.refresh_from_db()
        self.assertEqual(self.category.token_rate, Decimal("2.75"))
        self.assertTrue(response.context["formset"].forms[0].errors)

    def test_operational_pages_reject_anonymous_customers_and_collectors(self):
        urls = (
            reverse("admin_analytics_dashboard"), reverse("admin_token_rates"),
            reverse("marketplace_preparation"), reverse("admin_rewards"),
            reverse("admin_redemptions"), reverse("collector_applications"),
            reverse("admin_collection_requests"), reverse("admin_collection_history"),
            reverse("admin_wallet_activity"), reverse("admin_published_materials"),
            reverse("admin_buyer_requests"), reverse("admin_cashout_requests"),
        )
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        for user in (self.customer, self.collector):
            self.client.force_login(user)
            for url in urls:
                with self.subTest(user=user.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)


    def test_admin_can_review_and_approve_or_reject_collector_applications(self):
        pending_user = User.objects.create_user(username="pending_collector", role=User.Role.COLLECTOR)
        profile = CollectorProfile.objects.create(
            user=pending_user, identification_reference="ID-123", address="Stone Town",
        )
        listing = self.client.get(reverse("collector_applications"))
        self.assertContains(listing, "pending_collector")
        detail_url = reverse("collector_application_detail", args=[profile.pk])
        self.assertContains(self.client.get(detail_url), "ID-123")
        self.assertRedirects(self.client.post(detail_url, {"status": "approved"}), detail_url)
        profile.refresh_from_db()
        pending_user.refresh_from_db()
        self.assertEqual(profile.verification_status, CollectorProfile.VerificationStatus.APPROVED)
        self.assertEqual(pending_user.collector_verification_status, User.CollectorVerificationStatus.APPROVED)
        self.client.post(detail_url, {"status": "rejected"})
        profile.refresh_from_db()
        pending_user.refresh_from_db()
        self.assertEqual(profile.verification_status, CollectorProfile.VerificationStatus.REJECTED)
        self.assertEqual(pending_user.collector_verification_status, User.CollectorVerificationStatus.REJECTED)

    def test_custom_collection_queue_and_history_show_reward_snapshot_and_preparation(self):
        material = self.make_completed_preparation()
        from apps.wallet.models import Wallet, WalletTransaction
        collection = material.source_collection
        reward = WalletTransaction.objects.create(
            wallet=Wallet.objects.get_or_create(user=collection.waste_report.customer)[0],
            transaction_type=WalletTransaction.TransactionType.COLLECTION_REWARD,
            amount=Decimal("8.50"), description="Collection reward", collection=collection,
            collection_reward_unit="kg", collection_reward_quantity=Decimal("4.25"),
            collection_reward_rate=Decimal("2.00"), collection_reward_material="Plastic",
        )
        queue = self.client.get(reverse("admin_collection_requests"))
        self.assertContains(queue, "Collection #")
        self.assertContains(queue, "8.50 tokens")
        history = self.client.get(reverse("admin_collection_history"))
        self.assertContains(history, "4.25")
        self.assertContains(history, "Ready for preparation")
        self.assertEqual(history.context["rows"][0]["reward"], reward)

    def test_token_rate_active_status_is_editable(self):
        response = self.client.post(reverse("admin_token_rates"), {
            "rates-TOTAL_FORMS": "1", "rates-INITIAL_FORMS": "1",
            "rates-MIN_NUM_FORMS": "0", "rates-MAX_NUM_FORMS": "1000",
            "rates-0-id": str(self.category.pk), "rates-0-reward_unit": "kg",
            "rates-0-token_rate": "3.25", "rates-0-active": "on",
        })
        self.assertRedirects(response, reverse("admin_token_rates"))
        self.category.refresh_from_db()
        self.assertTrue(self.category.active)
        self.assertEqual(self.category.token_rate, Decimal("3.25"))

    def make_completed_preparation(self):
        customer = User.objects.create_user(username="material_owner", password="Strong-pass-123!")
        report = WasteReport.objects.create(
            customer=customer, category=self.category, description="Private collected bottles",
            estimated_weight=Decimal("8.00"), weight_unit=WasteReport.WeightUnit.KILOGRAMS,
            latitude=Decimal("-6.165900"), longitude=Decimal("39.202600"), location_accuracy=Decimal("5.00"),
            status=WasteReport.Status.COLLECTED,
        )
        collection = CollectionRequest.objects.create(
            waste_report=report, status=CollectionRequest.Status.COMPLETED,
            actual_weight=Decimal("4.25"), weight_unit=WasteReport.WeightUnit.KILOGRAMS,
        )
        material = MarketplaceMaterial.objects.create(
            name="Plastic", category=self.category, available_quantity=Decimal("4.25"),
            unit=MarketplaceMaterial.Unit.KILOGRAM, active=False,
            preparation_status=MarketplaceMaterial.PreparationStatus.READY,
            source_collection=collection,
        )
        return material

    def prep_data(self, material, status, **overrides):
        values = {
            "name": "Sorted PET Plastic", "description": "Washed and sorted PET plastic.",
            "category": self.category.pk, "available_quantity": "4.25", "unit": "kg",
            "price_per_unit": "900.50", "preparation_status": status,
        }
        values.update(overrides)
        return values

    def test_admin_can_save_draft_then_explicitly_publish_material(self):
        material = self.make_completed_preparation()
        edit_url = reverse("marketplace_preparation_edit", args=[material.pk])
        self.assertEqual(self.client.get(reverse("marketplace_preparation")).status_code, 200)
        draft_response = self.client.post(edit_url, self.prep_data(material, "draft"))
        self.assertRedirects(draft_response, reverse("marketplace_preparation"))
        material.refresh_from_db()
        self.assertFalse(material.active)
        self.assertEqual(material.preparation_status, MarketplaceMaterial.PreparationStatus.DRAFT)
        self.assertNotContains(self.client.get(reverse("marketplace")), "Sorted PET Plastic")

        publish_response = self.client.post(edit_url, self.prep_data(material, "published"))
        self.assertRedirects(publish_response, reverse("marketplace_preparation"))
        material.refresh_from_db()
        self.assertTrue(material.active)
        self.assertIsNotNone(material.published_at)
        public = self.client.get(reverse("marketplace"))
        self.assertContains(public, "Sorted PET Plastic")
        self.assertNotContains(public, "Private collected bottles")
        detail = self.client.get(reverse("marketplace_material_detail", args=[material.pk]))
        self.assertContains(detail, "Washed and sorted PET plastic.")
        self.assertNotContains(detail, "material_owner")

    def test_publish_requires_public_details_and_positive_stock(self):
        material = self.make_completed_preparation()
        response = self.client.post(
            reverse("marketplace_preparation_edit", args=[material.pk]),
            self.prep_data(material, "published", description="", available_quantity="0"),
        )
        self.assertEqual(response.status_code, 200)
        material.refresh_from_db()
        self.assertFalse(material.active)
        self.assertEqual(material.preparation_status, MarketplaceMaterial.PreparationStatus.READY)

    def test_reward_store_management_uses_reward_model(self):
        response = self.client.post(reverse("admin_reward_create"), {
            "name": "Reusable Bag", "description": "A reward bag", "token_cost": "12.50",
            "inventory": "7", "active": "on",
        })
        self.assertRedirects(response, reverse("admin_rewards"))
        reward = self.client.get(reverse("admin_rewards"))
        self.assertContains(reward, "Reusable Bag")
        self.assertEqual(reward.context["rewards"].get().token_cost, Decimal("12.50"))
