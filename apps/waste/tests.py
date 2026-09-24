from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User

from .models import WasteCategory, WasteReport


class WasteReportingTests(TestCase):
    def setUp(self):
        self.category = WasteCategory.objects.create(name="Plastic", active=True)
        self.inactive_category = WasteCategory.objects.create(name="Glass", active=False)
        self.customer = User.objects.create_user(username="customer", password="Strong-pass-123!")
        self.collector = User.objects.create_user(
            username="collector",
            password="Strong-pass-123!",
            role=User.Role.COLLECTOR,
        )
        self.report_data = {
            "category": self.category.id,
            "description": "Clean plastic bottles",
            "estimated_weight": "2.50",
            "weight_unit": "kg",
            "latitude": "-6.1659",
            "longitude": "39.2026",
            "location_accuracy": "12.50",
        }

    def test_anonymous_user_cannot_access_report_creation(self):
        response = self.client.get(reverse("waste_report_create"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('waste_report_create')}")

    def test_customer_can_access_report_creation(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("waste_report_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plastic")

    def test_collector_cannot_create_waste_report(self):
        self.client.force_login(self.collector)
        response = self.client.get(reverse("waste_report_create"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_customer_can_create_valid_waste_report(self):
        self.client.force_login(self.customer)
        response = self.client.post(reverse("waste_report_create"), self.report_data)
        report = WasteReport.objects.get()
        self.assertRedirects(response, reverse("waste_report_detail", args=[report.id]))
        self.assertEqual(report.customer, self.customer)
        self.assertEqual(report.status, WasteReport.Status.SUBMITTED)

    def test_piece_category_accepts_piece_estimate_without_kg_estimate(self):
        self.category.reward_unit = WasteCategory.RewardUnit.PIECE
        self.category.save(update_fields=["reward_unit", "updated_at"])
        self.client.force_login(self.customer)
        data = {key: value for key, value in self.report_data.items() if key not in {"estimated_weight", "weight_unit"}}
        data["estimated_piece_count"] = "75"
        response = self.client.post(reverse("waste_report_create"), data)
        self.assertEqual(response.status_code, 302)
        report = WasteReport.objects.get()
        self.assertRedirects(response, reverse("waste_report_detail", args=[report.pk]))
        self.assertIsNone(report.estimated_weight)
        self.assertEqual(report.estimated_piece_count, Decimal("75"))

    def test_customer_is_automatically_assigned_to_report(self):
        self.client.force_login(self.customer)
        self.client.post(reverse("waste_report_create"), self.report_data)
        self.assertEqual(WasteReport.objects.get().customer, self.customer)

    def test_new_report_status_is_submitted(self):
        self.client.force_login(self.customer)
        self.client.post(reverse("waste_report_create"), self.report_data)
        self.assertEqual(WasteReport.objects.get().status, WasteReport.Status.SUBMITTED)

    def test_invalid_latitude_is_rejected(self):
        self.client.force_login(self.customer)
        data = {**self.report_data, "latitude": "91"}
        response = self.client.post(reverse("waste_report_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WasteReport.objects.count(), 0)

    def test_invalid_longitude_is_rejected(self):
        self.client.force_login(self.customer)
        data = {**self.report_data, "longitude": "181"}
        response = self.client.post(reverse("waste_report_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WasteReport.objects.count(), 0)

    def test_customer_can_only_see_their_own_reports(self):
        other_customer = User.objects.create_user(username="other", password="Strong-pass-123!")
        own_report = WasteReport.objects.create(
            customer=self.customer,
            category=self.category,
            **self.report_data_without_category(),
        )
        WasteReport.objects.create(
            customer=other_customer,
            category=self.category,
            **self.report_data_without_category(),
        )
        self.client.force_login(self.customer)
        response = self.client.get(reverse("waste_report_list"))
        self.assertContains(response, own_report.category.name)
        self.assertEqual(response.context["reports"].count(), 1)

    def test_customer_cannot_view_another_customers_report(self):
        other_customer = User.objects.create_user(username="other", password="Strong-pass-123!")
        other_report = WasteReport.objects.create(
            customer=other_customer,
            category=self.category,
            **self.report_data_without_category(),
        )
        self.client.force_login(self.customer)
        response = self.client.get(reverse("waste_report_detail", args=[other_report.id]))
        self.assertEqual(response.status_code, 404)

    def test_waste_categories_are_loaded_from_active_database_categories(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("waste_report_create"))
        choices = list(response.context["form"].fields["category"].queryset)
        self.assertEqual(choices, [self.category])

    def test_inactive_categories_cannot_be_selected(self):
        self.client.force_login(self.customer)
        data = {**self.report_data, "category": self.inactive_category.id}
        response = self.client.post(reverse("waste_report_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WasteReport.objects.count(), 0)

    def report_data_without_category(self):
        return {
            "description": "Clean plastic bottles",
            "estimated_weight": Decimal("2.50"),
            "weight_unit": "kg",
            "latitude": Decimal("-6.1659"),
            "longitude": Decimal("39.2026"),
            "location_accuracy": Decimal("12.50"),
        }
