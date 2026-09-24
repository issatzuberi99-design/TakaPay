from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.waste.models import WasteCategory

from .models import BuyerRequest, MarketplaceMaterial


class MarketplaceTestMixin:
    def material(self, **overrides):
        values = {
            "name": "Recycled Plastic",
            "description": "Clean plastic ready for recycling.",
            "category": self.category,
            "available_quantity": Decimal("500.00"),
            "unit": MarketplaceMaterial.Unit.KILOGRAM,
            "price_per_unit": Decimal("1000.00"),
            "active": True,
        }
        values.update(overrides)
        return MarketplaceMaterial.objects.create(**values)


class MarketplacePublicTests(MarketplaceTestMixin, TestCase):
    def setUp(self):
        self.category = WasteCategory.objects.create(name="Plastic", active=True)
        self.active_material = self.material()
        self.inactive_material = self.material(name="Hidden", active=False)
        self.empty_material = self.material(name="Empty", available_quantity=Decimal("0.00"))

    def test_anonymous_user_can_browse_only_available_materials(self):
        response = self.client.get(reverse("marketplace"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.active_material.name)
        self.assertNotContains(response, self.inactive_material.name)
        self.assertNotContains(response, self.empty_material.name)

    def test_available_material_detail_is_public(self):
        response = self.client.get(reverse("marketplace_material_detail", args=[self.active_material.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.active_material.description)
        self.assertContains(response, "Request material")

    def test_inactive_and_empty_materials_are_not_public(self):
        self.assertEqual(self.client.get(reverse("marketplace_material_detail", args=[self.inactive_material.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("marketplace_material_detail", args=[self.empty_material.pk])).status_code, 404)

    def test_material_image_is_optional(self):
        material = self.material(image="")
        self.assertFalse(material.image)

    def test_public_pages_do_not_expose_buyer_information(self):
        BuyerRequest.objects.create(
            buyer_name="Private Buyer", company_name="Private Company", phone_number="0712345678",
            email="private@example.com", location="Private Location", material=self.active_material,
            material_name=self.active_material.name, requested_quantity=Decimal("1.00"), unit=self.active_material.unit,
        )
        for url in (reverse("marketplace"), reverse("marketplace_material_detail", args=[self.active_material.pk])):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            for private_value in ("Private Buyer", "0712345678", "private@example.com", "Private Location"):
                self.assertNotContains(response, private_value)

    def test_buyer_requests_have_no_public_listing(self):
        response = self.client.get("/marketplace/requests/")
        self.assertEqual(response.status_code, 404)


class BuyerRequestTests(MarketplaceTestMixin, TestCase):
    def setUp(self):
        self.category = WasteCategory.objects.create(name="Aluminum", active=True)
        self.material_record = self.material()

    def data(self, **overrides):
        values = {
            "buyer_name": "Asha Buyer",
            "company_name": "Green Works",
            "phone_number": "0712345678",
            "email": "buyer@example.com",
            "location": "Stone Town",
            "requested_quantity": "100.00",
            "message": "Please contact me.",
        }
        values.update(overrides)
        return values

    def submit(self, **overrides):
        return self.client.post(
            reverse("buyer_request_create", args=[self.material_record.pk]),
            self.data(**overrides),
        )

    def test_anonymous_buyer_can_submit_and_sees_confirmation(self):
        response = self.submit()
        request_record = BuyerRequest.objects.get()
        self.assertRedirects(response, reverse("buyer_request_confirmation", args=[request_record.pk]))
        confirmation = self.client.get(response.url)
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "TP-000001")
        self.assertContains(confirmation, request_record.material_name)
        self.assertContains(confirmation, "100.00")
        self.assertContains(confirmation, "Pending")
        self.assertContains(confirmation, "The TakaPay team will review your request")
        self.assertEqual(request_record.status, BuyerRequest.Status.PENDING)
        self.assertEqual(request_record.material, self.material_record)
        self.assertEqual(request_record.material_name, self.material_record.name)
        self.assertEqual(request_record.price_per_unit, Decimal("1000.00"))
        self.assertEqual(request_record.unit, MarketplaceMaterial.Unit.KILOGRAM)
        self.assertEqual(request_record.buyer_name, "Asha Buyer")
        self.assertEqual(request_record.phone_number, "0712345678")
        self.assertEqual(request_record.email, "buyer@example.com")
        self.assertEqual(request_record.location, "Stone Town")
        self.material_record.refresh_from_db()
        self.assertEqual(self.material_record.available_quantity, Decimal("500.00"))

    def test_confirmation_does_not_expose_buyer_details_or_work_without_session(self):
        self.submit()
        request_record = BuyerRequest.objects.get()
        response = self.client.get(reverse("buyer_request_confirmation", args=[request_record.pk]))
        for private_value in (request_record.buyer_name, request_record.email, request_record.phone_number, request_record.location):
            self.assertNotContains(response, private_value)
        self.assertEqual(self.client.session["marketplace_confirmation_id"], request_record.pk)
        self.assertEqual(self.client_class().get(response.request["PATH_INFO"]).status_code, 404)

    def test_request_for_unavailable_material_is_not_accepted(self):
        self.material_record.active = False
        self.material_record.save(update_fields=["active"])
        response = self.submit()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(BuyerRequest.objects.count(), 0)

    def test_posted_material_id_cannot_change_url_selected_material(self):
        other = self.material(name="Glass")
        self.submit(material_id=other.pk)
        self.assertEqual(BuyerRequest.objects.get().material, self.material_record)

    def test_public_post_cannot_set_status_or_inventory(self):
        response = self.submit(status=BuyerRequest.Status.COMPLETED, available_quantity="1", price_per_unit="0")
        self.assertEqual(response.status_code, 302)
        request_record = BuyerRequest.objects.get()
        self.assertEqual(request_record.status, BuyerRequest.Status.PENDING)
        self.assertEqual(request_record.price_per_unit, Decimal("1000.00"))
        self.material_record.refresh_from_db()
        self.assertEqual(self.material_record.available_quantity, Decimal("500.00"))

    def test_invalid_and_whitespace_only_buyer_data_is_rejected(self):
        cases = [
            {"buyer_name": ""}, {"buyer_name": "   "}, {"phone_number": ""},
            {"phone_number": "   "}, {"email": ""}, {"email": "invalid"},
            {"location": ""}, {"location": "   "}, {"requested_quantity": ""},
            {"requested_quantity": "0"}, {"requested_quantity": "-1"},
            {"requested_quantity": "501"},
        ]
        for case in cases:
            with self.subTest(case=case):
                response = self.submit(**case)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(BuyerRequest.objects.count(), 0)


class MarketplaceAdminWorkflowTests(MarketplaceTestMixin, TestCase):
    def setUp(self):
        self.category = WasteCategory.objects.create(name="Cardboard", active=True)
        self.material_record = self.material()
        self.customer = User.objects.create_user(username="buyer_admin_test", password="Strong-pass-123!", role=User.Role.CUSTOMER)
        self.collector = User.objects.create_user(username="market_collector", password="Strong-pass-123!", role=User.Role.COLLECTOR)
        self.admin = User.objects.create_superuser(username="market_admin", email="admin@example.com", password="Strong-pass-123!")
        self.request_record = BuyerRequest.objects.create(
            buyer_name="Buyer", phone_number="0712345678", email="buyer@example.com", location="Zanzibar",
            material=self.material_record, material_name=self.material_record.name,
            requested_quantity=Decimal("100.00"), unit=self.material_record.unit,
            price_per_unit=self.material_record.price_per_unit,
        )

    def test_only_admin_can_access_material_and_buyer_request_admin(self):
        change_url = reverse("admin:marketplace_buyerrequest_change", args=[self.request_record.pk])
        changelist_url = reverse("admin:marketplace_marketplacematerial_changelist")
        for user in (None, self.customer, self.collector):
            if user:
                self.client.force_login(user)
            response = self.client.get(changelist_url)
            self.assertIn(response.status_code, (302, 403))
            response = self.client.get(change_url)
            self.assertIn(response.status_code, (302, 403))
            self.client.logout()
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(changelist_url).status_code, 200)
        self.assertEqual(self.client.get(change_url).status_code, 200)

    def test_admin_can_process_and_complete_request_once(self):
        self.request_record.transition_to(BuyerRequest.Status.PROCESSING, self.admin)
        self.request_record.transition_to(BuyerRequest.Status.COMPLETED, self.admin)
        self.material_record.refresh_from_db()
        self.assertEqual(self.material_record.available_quantity, Decimal("400.00"))
        with self.assertRaises(ValidationError):
            self.request_record.transition_to(BuyerRequest.Status.PROCESSING, self.admin)
        self.material_record.refresh_from_db()
        self.assertEqual(self.material_record.available_quantity, Decimal("400.00"))

    def test_pending_request_can_be_rejected_or_cancelled_without_inventory_change(self):
        self.request_record.transition_to(BuyerRequest.Status.REJECTED, self.admin)
        self.material_record.refresh_from_db()
        self.assertEqual(self.material_record.available_quantity, Decimal("500.00"))
        with self.assertRaises(ValidationError):
            self.request_record.transition_to(BuyerRequest.Status.COMPLETED, self.admin)
        second_request = BuyerRequest.objects.create(
            buyer_name="Another", phone_number="0712345678", email="another@example.com", location="Zanzibar",
            material=self.material_record, material_name=self.material_record.name,
            requested_quantity=Decimal("10.00"), unit=self.material_record.unit,
        )
        second_request.transition_to(BuyerRequest.Status.CANCELLED, self.admin)
        self.assertEqual(second_request.status, BuyerRequest.Status.CANCELLED)

    def test_invalid_status_transition_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.request_record.transition_to(BuyerRequest.Status.COMPLETED, self.admin)
        self.request_record.transition_to(BuyerRequest.Status.PROCESSING, self.admin)
        self.request_record.transition_to(BuyerRequest.Status.COMPLETED, self.admin)
        with self.assertRaises(ValidationError):
            self.request_record.transition_to(BuyerRequest.Status.PENDING, self.admin)

    def test_completion_fails_safely_when_inventory_is_insufficient(self):
        self.request_record.transition_to(BuyerRequest.Status.PROCESSING, self.admin)
        self.material_record.available_quantity = Decimal("50.00")
        self.material_record.save(update_fields=["available_quantity", "updated_at"])
        with self.assertRaises(ValidationError):
            self.request_record.transition_to(BuyerRequest.Status.COMPLETED, self.admin)
        self.request_record.refresh_from_db()
        self.material_record.refresh_from_db()
        self.assertEqual(self.request_record.status, BuyerRequest.Status.PROCESSING)
        self.assertEqual(self.material_record.available_quantity, Decimal("50.00"))

    def test_admin_can_change_status_through_admin(self):
        self.client.force_login(self.admin)
        url = reverse("admin:marketplace_buyerrequest_change", args=[self.request_record.pk])
        response = self.client.post(url, {"status": BuyerRequest.Status.PROCESSING, "admin_notes": "Reviewed", "_save": "Save"})
        self.assertEqual(response.status_code, 302)
        self.request_record.refresh_from_db()
        self.assertEqual(self.request_record.status, BuyerRequest.Status.PROCESSING)
        self.assertEqual(self.request_record.admin_notes, "Reviewed")
