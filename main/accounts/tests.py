"""Tests for email-verification state, the flow around it and soft enforcement."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .emails import mark_verified, send_verification_email, verification_url
from .models import EmailVerification, email_is_verified
from .tokens import email_verification_token

User = get_user_model()


def make_user(email="student@example.edu", **kwargs):
    return User.objects.create_user(username=email, email=email, password="pass12345", **kwargs)


def verify_path(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    return reverse("accounts:verify_email", kwargs={"uidb64": uid, "token": token})


class EmailVerificationModelTests(TestCase):
    def test_new_account_is_unverified(self):
        user = make_user()
        record, _ = EmailVerification.objects.get_or_create(user=user)
        self.assertFalse(record.is_verified)
        self.assertFalse(email_is_verified(user))

    def test_mark_verified_is_idempotent(self):
        user = make_user()
        self.assertTrue(mark_verified(user))
        self.assertTrue(email_is_verified(user))
        self.assertFalse(mark_verified(user))

    def test_email_is_verified_handles_anonymous(self):
        self.assertFalse(email_is_verified(None))


class VerificationFlowTests(TestCase):
    def test_send_then_verify_marks_account(self):
        user = make_user()
        self.assertTrue(send_verification_email(user))
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(email_is_verified(user))

        response = self.client.post(verify_path(user))
        self.assertIn(response.status_code, (302, 200))
        user.refresh_from_db()
        self.assertTrue(email_is_verified(user))

    def test_get_does_not_auto_verify(self):
        user = make_user()
        send_verification_email(user)
        response = self.client.get(verify_path(user))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(email_is_verified(user))

    def test_bad_token_does_not_verify(self):
        user = make_user()
        bad = reverse(
            "accounts:verify_email",
            kwargs={"uidb64": urlsafe_base64_encode(force_bytes(user.pk)), "token": "bad-token"},
        )
        self.client.post(bad)
        self.assertFalse(email_is_verified(user))

    def test_resend_is_throttled(self):
        user = make_user()
        self.assertTrue(send_verification_email(user))
        self.assertFalse(send_verification_email(user))
        self.assertEqual(len(mail.outbox), 1)

    def test_verification_url_contains_site_url(self):
        user = make_user()
        self.assertIn("/verify-email/", verification_url(user))

    def test_register_sends_confirmation_email(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "email": "newbie@example.edu",
                "password1": "a-very-strong-pass-1",
                "password2": "a-very-strong-pass-1",
                "agree": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        user = User.objects.get(email="newbie@example.edu")
        self.assertFalse(email_is_verified(user))


@override_settings(EMAIL_VERIFICATION_REQUIRED=True)
class EnforcementMiddlewareTests(TestCase):
    def test_unverified_user_is_redirected(self):
        user = make_user()
        self.client.force_login(user)
        response = self.client.get(reverse("campus:dashboard"))
        self.assertRedirects(response, reverse("accounts:verify_email_notice"))

    def test_verification_page_is_reachable(self):
        user = make_user()
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:verify_email_notice"))
        self.assertEqual(response.status_code, 200)

    def test_verified_user_is_not_redirected(self):
        user = make_user()
        mark_verified(user)
        self.client.force_login(user)
        response = self.client.get(reverse("campus:dashboard"))
        self.assertNotEqual(
            response.get("Location", ""), reverse("accounts:verify_email_notice")
        )

    def test_staff_bypasses_enforcement(self):
        user = make_user(email="staff@example.edu", is_staff=True)
        self.client.force_login(user)
        response = self.client.get(reverse("campus:dashboard"))
        self.assertNotEqual(
            response.get("Location", ""), reverse("accounts:verify_email_notice")
        )
