from django.test import TestCase
from django.urls import reverse

from .models import CollectorProfile, User


class AuthenticationTests(TestCase):
    def customer_data(self):
        return {
            "first_name": "Asha",
            "last_name": "Ali",
            "username": "asha",
            "email": "asha@example.com",
            "phone_number": "+255700000001",
            "password1": "Strong-pass-123!",
            "password2": "Strong-pass-123!",
        }

    def collector_data(self):
        data = self.customer_data()
        data.update(
            {
                "username": "collector",
                "email": "collector@example.com",
                "identification_reference": "ZAN-12345",
                "address": "Stone Town, Zanzibar",
            }
        )
        return data

    def test_customer_registration_creates_customer(self):
        response = self.client.post(reverse("register"), self.customer_data())
        user = User.objects.get(username="asha")
        self.assertRedirects(response, reverse("login"))
        self.assertEqual(user.role, User.Role.CUSTOMER)

    def test_collector_registration_creates_pending_profile(self):
        response = self.client.post(reverse("collector_register"), self.collector_data())
        user = User.objects.get(username="collector")
        self.assertRedirects(response, reverse("login"))
        self.assertEqual(user.role, User.Role.COLLECTOR)
        self.assertEqual(user.collector_profile.verification_status, CollectorProfile.VerificationStatus.PENDING)

    def test_public_registration_cannot_create_admin(self):
        data = self.customer_data()
        data["role"] = User.Role.ADMIN
        self.client.post(reverse("register"), data)
        user = User.objects.get(username="asha")
        self.assertEqual(user.role, User.Role.CUSTOMER)

    def test_pending_collector_cannot_access_collection_jobs(self):
        self.client.post(reverse("collector_register"), self.collector_data())
        self.client.login(username="collector", password="Strong-pass-123!")
        response = self.client.get(reverse("collector_jobs"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_approved_collector_can_access_collection_jobs(self):
        self.client.post(reverse("collector_register"), self.collector_data())
        profile = CollectorProfile.objects.get(user__username="collector")
        profile.verification_status = CollectorProfile.VerificationStatus.APPROVED
        profile.save()
        self.client.login(username="collector", password="Strong-pass-123!")
        response = self.client.get(reverse("collector_jobs"))
        self.assertEqual(response.status_code, 200)

    def test_customer_cannot_access_collection_jobs(self):
        self.client.post(reverse("register"), self.customer_data())
        self.client.login(username="asha", password="Strong-pass-123!")
        response = self.client.get(reverse("collector_jobs"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_user_can_log_in_with_username(self):
        User.objects.create_user(username="asha", password="Strong-pass-123!")
        response = self.client.post(reverse("login"), {"identifier": "asha", "password": "Strong-pass-123!"})
        self.assertRedirects(response, reverse("dashboard"))

    def test_user_can_log_in_with_email(self):
        User.objects.create_user(username="asha", email="asha@example.com", password="Strong-pass-123!")
        response = self.client.post(reverse("login"), {"identifier": "asha@example.com", "password": "Strong-pass-123!"})
        self.assertRedirects(response, reverse("dashboard"))

    def test_user_can_log_out(self):
        user = User.objects.create_user(username="asha", password="Strong-pass-123!")
        self.client.force_login(user)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)