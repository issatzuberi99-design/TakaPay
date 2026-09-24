from decimal import Decimal
from io import BytesIO

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CollectorProfile, User
from apps.waste.models import WasteCategory, WasteReport

from .models import CollectionRequest


class CollectionRequestTests(TestCase):
    def setUp(self):
        self.category = WasteCategory.objects.create(name="Plastic", active=True)
        self.customer = User.objects.create_user(username="customer", password="Strong-pass-123!")
        self.approved_collector = User.objects.create_user(
            username="approved_collector",
            password="Strong-pass-123!",
            role=User.Role.COLLECTOR,
        )
        CollectorProfile.objects.create(
            user=self.approved_collector,
            verification_status=CollectorProfile.VerificationStatus.APPROVED,
            identification_reference="COL-100",
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

    def test_collection_request_creation_uses_available_status_by_default(self):
        self.assertEqual(self.collection.status, CollectionRequest.Status.AVAILABLE)

    def test_collection_request_links_to_waste_report(self):
        self.assertEqual(self.collection.waste_report, self.report)

    def test_submitting_report_creates_collection_request(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("waste_report_create"),
            {
                "category": self.category.id,
                "description": "New report",
                "estimated_weight": "2.00",
                "weight_unit": WasteReport.WeightUnit.KILOGRAMS,
                "latitude": "-6.1659",
                "longitude": "39.2026",
                "location_accuracy": "12.00",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(WasteReport.objects.filter(description="New report").exists())
        self.assertEqual(WasteReport.objects.filter(description="New report").count(), 1)
        self.assertTrue(CollectionRequest.objects.filter(waste_report__description="New report").exists())

    def test_duplicate_collection_request_is_not_created(self):
        self.assertEqual(CollectionRequest.objects.filter(waste_report=self.report).count(), 1)
        CollectionRequest.objects.get_or_create(waste_report=self.report)
        self.assertEqual(CollectionRequest.objects.filter(waste_report=self.report).count(), 1)

    def test_approved_collector_can_access_dashboard(self):
        self.client.force_login(self.approved_collector)
        response = self.client.get(reverse("collections_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_available_unassigned_request_is_shown_and_hides_empty_state(self):
        self.assertIsNone(self.collection.collector)
        self.client.force_login(self.approved_collector)
        response = self.client.get(reverse("collections_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plastic bottles")
        self.assertNotContains(response, "No collection requests are currently available.")

    def test_empty_state_is_shown_when_no_available_jobs_exist(self):
        self.collection.status = CollectionRequest.Status.CANCELLED
        self.collection.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.approved_collector)
        response = self.client.get(reverse("collections_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No collection requests are currently available.")

    def test_assigned_accepted_request_is_not_available_to_other_collector(self):
        another_collector = User.objects.create_user(
            username="another_collector",
            password="Strong-pass-123!",
            role=User.Role.COLLECTOR,
        )
        CollectorProfile.objects.create(
            user=another_collector,
            verification_status=CollectorProfile.VerificationStatus.APPROVED,
            identification_reference="COL-103",
            address="Chake Chake",
        )
        self.collection.collector = self.approved_collector
        self.collection.status = CollectionRequest.Status.ACCEPTED
        self.collection.save()
        self.client.force_login(another_collector)
        response = self.client.get(reverse("collections_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.report.description)
        self.client.post(reverse("collection_accept", args=[self.collection.id]))
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.collector, self.approved_collector)
        self.assertEqual(self.collection.status, CollectionRequest.Status.ACCEPTED)

    def test_completed_and_cancelled_requests_are_not_available(self):
        self.collection.status = CollectionRequest.Status.COMPLETED
        self.collection.save(update_fields=["status", "updated_at"])
        cancelled_report = WasteReport.objects.create(
            customer=self.customer,
            category=self.category,
            description="Cancelled report",
            estimated_weight=Decimal("1.00"),
            weight_unit=WasteReport.WeightUnit.KILOGRAMS,
            latitude=Decimal("-6.1659"),
            longitude=Decimal("39.2026"),
            location_accuracy=Decimal("15.00"),
            status=WasteReport.Status.SUBMITTED,
        )
        cancelled = CollectionRequest.objects.create(
            waste_report=cancelled_report,
            status=CollectionRequest.Status.CANCELLED,
        )
        self.client.force_login(self.approved_collector)
        response = self.client.get(reverse("collections_dashboard"))
        self.assertNotContains(response, self.report.description)
        self.assertNotContains(response, cancelled_report.description)
        self.assertContains(response, "No collection requests are currently available.")

    def test_customer_cannot_access_collector_dashboard(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("collections_dashboard"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_pending_collector_cannot_access_dashboard(self):
        pending_collector = User.objects.create_user(
            username="pending_collector",
            password="Strong-pass-123!",
            role=User.Role.COLLECTOR,
        )
        CollectorProfile.objects.create(
            user=pending_collector,
            verification_status=CollectorProfile.VerificationStatus.PENDING,
            identification_reference="COL-101",
            address="Mtoni",
        )
        self.client.force_login(pending_collector)
        response = self.client.get(reverse("collections_dashboard"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_anonymous_user_cannot_access_collector_dashboard(self):
        response = self.client.get(reverse("collections_dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('collections_dashboard')}")

    def test_customer_cannot_access_collector_dashboard_via_decorator(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("collections_dashboard"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_pending_collector_cannot_access_collector_dashboard_via_decorator(self):
        pending_collector = User.objects.create_user(
            username="pending_collector",
            password="Strong-pass-123!",
            role=User.Role.COLLECTOR,
        )
        CollectorProfile.objects.create(
            user=pending_collector,
            verification_status=CollectorProfile.VerificationStatus.PENDING,
            identification_reference="COL-101",
            address="Mtoni",
        )
        self.client.force_login(pending_collector)
        response = self.client.get(reverse("collections_dashboard"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_rejected_collector_cannot_access_collector_dashboard_via_decorator(self):
        rejected_collector = User.objects.create_user(
            username="rejected_collector",
            password="Strong-pass-123!",
            role=User.Role.COLLECTOR,
        )
        CollectorProfile.objects.create(
            user=rejected_collector,
            verification_status=CollectorProfile.VerificationStatus.REJECTED,
            identification_reference="COL-102",
            address="Mikungani",
        )
        self.client.force_login(rejected_collector)
        response = self.client.get(reverse("collections_dashboard"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_customer_can_see_collection_status_on_own_report(self):
        self.collection.collector = self.approved_collector
        self.collection.status = CollectionRequest.Status.ACCEPTED
        self.collection.accepted_at = self.collection.created_at
        self.collection.actual_weight = Decimal("2.25")
        self.collection.weight_unit = WasteReport.WeightUnit.KILOGRAMS
        self.collection.save()
        self.report.status = WasteReport.Status.COLLECTED
        self.report.save(update_fields=["status", "updated_at"])

        self.client.force_login(self.customer)
        response = self.client.get(reverse("waste_report_detail", args=[self.report.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Collected")
        self.assertContains(response, "2.25")

    def test_approved_collector_can_accept_available_request(self):
        self.client.force_login(self.approved_collector)
        response = self.client.post(reverse("collection_accept", args=[self.collection.id]))
        self.collection.refresh_from_db()
        self.report.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.collection.status, CollectionRequest.Status.ACCEPTED)
        self.assertEqual(self.collection.collector, self.approved_collector)
        self.assertIsNotNone(self.collection.accepted_at)
        self.assertEqual(self.report.status, WasteReport.Status.PENDING_COLLECTION)

    def test_get_request_cannot_accept_collection(self):
        self.client.force_login(self.approved_collector)
        response = self.client.get(reverse("collection_accept", args=[self.collection.id]))
        self.collection.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.collection.status, CollectionRequest.Status.AVAILABLE)
        self.assertIsNone(self.collection.collector)

    def test_second_collector_cannot_accept_already_accepted_request(self):
        another_collector = User.objects.create_user(
            username="another_collector",
            password="Strong-pass-123!",
            role=User.Role.COLLECTOR,
        )
        CollectorProfile.objects.create(
            user=another_collector,
            verification_status=CollectorProfile.VerificationStatus.APPROVED,
            identification_reference="COL-103",
            address="Chake Chake",
        )
        self.collection.collector = self.approved_collector
        self.collection.status = CollectionRequest.Status.ACCEPTED
        self.collection.accepted_at = self.collection.created_at
        self.collection.save()

        self.client.force_login(another_collector)
        response = self.client.post(reverse("collection_accept", args=[self.collection.id]))
        self.collection.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.collection.collector, self.approved_collector)
        self.assertEqual(self.collection.status, CollectionRequest.Status.ACCEPTED)

    def test_already_accepted_request_cannot_be_accepted_again(self):
        self.collection.collector = self.approved_collector
        self.collection.status = CollectionRequest.Status.ACCEPTED
        self.collection.accepted_at = self.collection.created_at
        self.collection.save()
        self.client.force_login(self.approved_collector)
        response = self.client.post(reverse("collection_accept", args=[self.collection.id]))
        self.collection.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.collection.status, CollectionRequest.Status.ACCEPTED)
        self.assertEqual(self.collection.collector, self.approved_collector)

    def test_completed_request_cannot_be_accepted(self):
        self.collection.collector = self.approved_collector
        self.collection.status = CollectionRequest.Status.COMPLETED
        self.collection.completed_at = self.collection.created_at
        self.collection.save()
        self.client.force_login(self.approved_collector)
        response = self.client.post(reverse("collection_accept", args=[self.collection.id]))
        self.collection.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.collection.status, CollectionRequest.Status.COMPLETED)

    def test_cancelled_request_cannot_be_accepted(self):
        self.collection.status = CollectionRequest.Status.CANCELLED
        self.collection.save()
        self.client.force_login(self.approved_collector)
        response = self.client.post(reverse("collection_accept", args=[self.collection.id]))
        self.collection.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.collection.status, CollectionRequest.Status.CANCELLED)

    def test_unrelated_collector_cannot_complete_collection(self):
        another_collector = User.objects.create_user(
            username="another_collector",
            password="Strong-pass-123!",
            role=User.Role.COLLECTOR,
        )
        CollectorProfile.objects.create(
            user=another_collector,
            verification_status=CollectorProfile.VerificationStatus.APPROVED,
            identification_reference="COL-102",
            address="Kizimkazi",
        )
        self.collection.collector = self.approved_collector
        self.collection.status = CollectionRequest.Status.ACCEPTED
        self.collection.save()
        self.client.force_login(another_collector)
        response = self.client.get(reverse("collection_complete", args=[self.collection.id]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("collections_dashboard"))

    def test_missing_actual_weight_prevents_completion(self):
        self.collection.collector = self.approved_collector
        self.collection.status = CollectionRequest.Status.ACCEPTED
        self.collection.save()
        self.client.force_login(self.approved_collector)
        image = Image.new("RGB", (10, 10), color="green")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        photo = SimpleUploadedFile("proof.png", buffer.getvalue(), content_type="image/png")
        response = self.client.post(
            reverse("collection_complete", args=[self.collection.id]),
            {"weight_unit": WasteReport.WeightUnit.KILOGRAMS, "proof_photo": photo, "notes": "Collected successfully."},
        )
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.status, CollectionRequest.Status.ACCEPTED)

    def test_zero_actual_weight_prevents_completion(self):
        self.collection.collector = self.approved_collector
        self.collection.status = CollectionRequest.Status.ACCEPTED
        self.collection.save()
        self.client.force_login(self.approved_collector)
        image = Image.new("RGB", (10, 10), color="green")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        photo = SimpleUploadedFile("proof.png", buffer.getvalue(), content_type="image/png")
        response = self.client.post(
            reverse("collection_complete", args=[self.collection.id]),
            {"actual_weight": "0", "weight_unit": WasteReport.WeightUnit.KILOGRAMS, "proof_photo": photo, "notes": "Collected successfully."},
        )
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.status, CollectionRequest.Status.ACCEPTED)

    def test_missing_proof_photo_prevents_completion(self):
        self.collection.collector = self.approved_collector
        self.collection.status = CollectionRequest.Status.ACCEPTED
        self.collection.save()
        self.client.force_login(self.approved_collector)
        response = self.client.post(
            reverse("collection_complete", args=[self.collection.id]),
            {"actual_weight": "2.00", "weight_unit": WasteReport.WeightUnit.KILOGRAMS, "notes": "Collected successfully."},
        )
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.status, CollectionRequest.Status.ACCEPTED)

    def test_assigned_collector_can_complete_collection(self):
        self.collection.collector = self.approved_collector
        self.collection.status = CollectionRequest.Status.ACCEPTED
        self.collection.save()
        self.client.force_login(self.approved_collector)
        image = Image.new("RGB", (10, 10), color="green")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        photo = SimpleUploadedFile("proof.png", buffer.getvalue(), content_type="image/png")
        response = self.client.post(
            reverse("collection_complete", args=[self.collection.id]),
            {
                "actual_weight": "2.00",
                "weight_unit": WasteReport.WeightUnit.KILOGRAMS,
                "proof_photo": photo,
                "notes": "Collected successfully.",
            },
        )
        self.collection.refresh_from_db()
        self.report.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.collection.status, CollectionRequest.Status.COMPLETED)
        self.assertEqual(self.report.status, WasteReport.Status.COLLECTED)
        self.assertTrue(self.collection.proof_photo)
        self.assertIsNotNone(self.collection.completed_at)
