"""Tests for email-verification state, the flow around it and soft enforcement."""

from __future__ import annotations

import datetime as dt
import smtplib
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .email_validation import suggest_email_correction
from .forms import RegisterForm, username_for_email
from .emails import (
    SendResult,
    deliver_verification_email,
    mark_verified,
    send_verification_email,
    verification_url,
)
from .models import EmailVerification, email_is_verified
from .tokens import email_verification_token

User = get_user_model()


def make_user(email="student@example.edu", **kwargs):
    return User.objects.create_user(username=email, email=email, password="pass12345", **kwargs)


def verify_path(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    return reverse("accounts:verify_email", kwargs={"uidb64": uid, "token": token})


def queue_and_deliver(user):
    result = send_verification_email(user)
    return result, deliver_verification_email(user.email_verification.pk)


def register_payload(email, **overrides):
    payload = {
        "email": email,
        "password1": "a-very-strong-pass-1",
        "password2": "a-very-strong-pass-1",
        "agree": "on",
    }
    payload.update(overrides)
    return payload


def email_of_length(length: int) -> str:
    """Build a syntactically valid address of exactly ``length`` characters."""

    local = "a" * 64
    suffix = ".example.com"
    remaining = length - len(local) - 1 - len(suffix)
    labels = []
    while remaining > 0:
        size = min(63, remaining)
        labels.append("b" * size)
        remaining -= size + 1
    email = f"{local}@{'.'.join(labels + ['example', 'com'])}"
    if len(email) != length:
        raise AssertionError(f"Built {len(email)} characters, expected {length}.")
    return email


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
        result = send_verification_email(user)
        self.assertTrue(result)
        self.assertEqual(result.reason, "queued")
        self.assertEqual(len(mail.outbox), 0)

        record = user.email_verification
        self.assertEqual(record.email_status, EmailVerification.EmailStatus.PENDING)
        self.assertTrue(deliver_verification_email(record.pk))
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

    @override_settings(PASSWORD_RESET_TIMEOUT=1)
    def test_expired_token_does_not_verify(self):
        user = make_user()
        path = verify_path(user)
        with mock.patch.object(
            email_verification_token,
            "_now",
            return_value=dt.datetime.now() + dt.timedelta(seconds=10),
        ):
            response = self.client.post(path)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(email_is_verified(user))

    def test_resend_is_throttled_after_successful_delivery(self):
        user = make_user()
        self.assertTrue(send_verification_email(user))
        again = send_verification_email(user)
        self.assertTrue(again)
        self.assertEqual(again.reason, "already_queued")
        self.assertTrue(deliver_verification_email(user.email_verification.pk))

        throttled = send_verification_email(user)
        self.assertFalse(throttled)
        self.assertEqual(throttled.reason, "throttled")
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_ignores_an_external_next_url(self):
        user = make_user()
        self.client.force_login(user)
        response = self.client.post(
            reverse("accounts:resend_verification"),
            {"next": "https://evil.example/phish"},
        )
        self.assertRedirects(response, reverse("accounts:verify_email_notice"))

    def test_verification_url_contains_site_url(self):
        user = make_user()
        self.assertIn("/verify-email/", verification_url(user))

    def test_register_queues_confirmation_email_without_claiming_delivery(self):
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
        user = User.objects.get(email="newbie@example.edu")
        self.assertEqual(
            user.email_verification.email_status,
            EmailVerification.EmailStatus.PENDING,
        )
        self.assertEqual(len(mail.outbox), 0)
        messages = [str(m) for m in response.wsgi_request._messages]
        self.assertFalse(any("emailed you a confirmation link" in m for m in messages), messages)
        self.assertTrue(any("sending a confirmation link" in m for m in messages), messages)

        self.assertTrue(deliver_verification_email(user.email_verification.pk))
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(email_is_verified(user))

    def test_verification_before_delivery_skips_the_queued_email(self):
        user = make_user()
        send_verification_email(user)
        mark_verified(user)
        self.assertFalse(deliver_verification_email(user.email_verification.pk))
        self.assertEqual(len(mail.outbox), 0)
        user.email_verification.refresh_from_db()
        self.assertEqual(
            user.email_verification.email_status,
            EmailVerification.EmailStatus.SKIPPED,
        )


class RegistrationEmailValidationTests(TestCase):
    def test_invalid_email_syntax_is_rejected(self):
        response = self.client.post(
            reverse("accounts:register"), register_payload("not-an-email")
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertFalse(User.objects.filter(email__iexact="not-an-email").exists())

    def test_common_domain_typo_is_flagged_with_suggestion(self):
        response = self.client.post(
            reverse("accounts:register"), register_payload("aman@gmial.com")
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.email_suggestion, "aman@gmail.com")
        self.assertIn("Did you mean aman@gmail.com?", form.errors["email"][0])
        self.assertFalse(User.objects.filter(email__iexact="aman@gmial.com").exists())

    def test_legitimate_custom_domain_is_accepted(self):
        response = self.client.post(
            reverse("accounts:register"), register_payload("aman@my-campus.example")
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="aman@my-campus.example").exists())

    def test_user_can_confirm_original_address_is_intentional(self):
        response = self.client.post(
            reverse("accounts:register"),
            register_payload("aman@gmial.com", confirm_email_typo="on"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="aman@gmial.com").exists())
        self.assertFalse(User.objects.filter(email="aman@gmail.com").exists())

    def test_user_can_accept_suggestion_explicitly(self):
        response = self.client.post(
            reverse("accounts:register"),
            register_payload("aman@gmial.com", use_suggested_email="1"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="aman@gmail.com").exists())
        self.assertFalse(User.objects.filter(email="aman@gmial.com").exists())

    def test_registration_creates_valid_but_unverified_email(self):
        response = self.client.post(
            reverse("accounts:register"), register_payload("newbie@example.edu")
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="newbie@example.edu")
        self.assertFalse(email_is_verified(user))
        self.assertFalse(user.email_verification.is_verified)

    def test_duplicate_registration_does_not_create_second_account(self):
        make_user(email="taken@example.edu")
        response = self.client.post(
            reverse("accounts:register"), register_payload("Taken@Example.EDU")
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(
            User.objects.filter(email__iexact="taken@example.edu").count(), 1
        )


class RegistrationEmailLengthTests(TestCase):
    def test_short_email_keeps_using_the_normalized_email_as_username(self):
        response = self.client.post(
            reverse("accounts:register"), register_payload("Student@Example.EDU")
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="student@example.edu")
        self.assertEqual(user.username, "student@example.edu")

    def test_model_max_length_email_is_accepted_with_deterministic_username(self):
        email = email_of_length(254)
        response = self.client.post(
            reverse("accounts:register"), register_payload(email)
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email=email)
        self.assertEqual(user.username, username_for_email(email))
        self.assertLessEqual(len(user.username), 150)
        self.assertEqual(
            user.email_verification.email_status,
            EmailVerification.EmailStatus.PENDING,
        )

    def test_email_over_model_max_length_is_rejected_without_account_or_outbox(self):
        for length in (255, 300, 320):
            with self.subTest(length=length):
                email = email_of_length(length)
                response = self.client.post(
                    reverse("accounts:register"), register_payload(email)
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("email", response.context["form"].errors)
                self.assertFalse(User.objects.filter(email=email).exists())
                self.assertFalse(EmailVerification.objects.exists())

    def test_long_email_concurrent_forms_cannot_both_create_an_account(self):
        email = email_of_length(200)
        first = RegisterForm(register_payload(email))
        second = RegisterForm(register_payload(email))
        self.assertTrue(first.is_valid())
        self.assertTrue(second.is_valid())

        first.save()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                second.save()

        self.assertEqual(User.objects.filter(email=email).count(), 1)

    def test_long_duplicate_email_is_rejected_by_form_validation(self):
        email = email_of_length(200)
        User.objects.create_user(
            username=username_for_email(email),
            email=email,
            password="pass12345",
        )
        response = self.client.post(
            reverse("accounts:register"), register_payload(email)
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(User.objects.filter(email=email).count(), 1)


class RegistrationOutboxSafetyTests(TestCase):
    def test_invalid_email_creates_no_account_or_outbox(self):
        response = self.client.post(
            reverse("accounts:register"), register_payload("not-an-email")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(EmailVerification.objects.count(), 0)

    def test_typo_suggestion_creates_no_account_or_outbox(self):
        response = self.client.post(
            reverse("accounts:register"), register_payload("aman@gmial.com")
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(EmailVerification.objects.count(), 0)

    def test_duplicate_registration_creates_no_new_outbox_row(self):
        user = make_user(email="taken@example.edu")
        EmailVerification.objects.create(user=user)
        response = self.client.post(
            reverse("accounts:register"), register_payload("Taken@Example.EDU")
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(EmailVerification.objects.count(), 1)


class EmailTypoSuggestionTests(TestCase):
    def test_only_exact_known_domains_are_suggested(self):
        self.assertEqual(suggest_email_correction("a@gmial.com"), "a@gmail.com")
        self.assertIsNone(suggest_email_correction("a@mygmial.com"))
        self.assertIsNone(suggest_email_correction("a@custom-campus.example"))

    @override_settings(
        EMAIL_DOMAIN_SUGGESTIONS={"campus.test": "campus.edu"}
    )
    def test_mapping_is_configurable(self):
        self.assertEqual(suggest_email_correction("a@campus.test"), "a@campus.edu")
        self.assertIsNone(suggest_email_correction("a@gmial.com"))


class VerificationOutboxTests(TestCase):
    def _break_smtp(self):
        return mock.patch(
            "config.mail._django_send_mail", side_effect=OSError("connection refused")
        )

    def test_duplicate_queue_does_not_send_twice(self):
        user = make_user()
        self.assertTrue(send_verification_email(user))
        self.assertTrue(send_verification_email(user))
        record = user.email_verification
        self.assertEqual(record.email_status, EmailVerification.EmailStatus.PENDING)
        self.assertEqual(record.email_attempts, 0)

        self.assertTrue(deliver_verification_email(record.pk))
        self.assertFalse(deliver_verification_email(record.pk))
        self.assertEqual(len(mail.outbox), 1)

    def test_failed_send_is_recorded_and_visible(self):
        user = make_user()
        self.assertTrue(send_verification_email(user))
        with self._break_smtp():
            with self.assertLogs("config.mail", level="ERROR"):
                self.assertFalse(deliver_verification_email(user.email_verification.pk))
        record = user.email_verification
        record.refresh_from_db()
        self.assertEqual(record.email_status, EmailVerification.EmailStatus.FAILED)
        self.assertEqual(record.email_attempts, 1)
        self.assertIsNone(record.sent_at)
        self.assertTrue(record.email_last_error)

    def test_failed_send_does_not_start_the_cooldown(self):
        user = make_user()
        send_verification_email(user)
        with self._break_smtp():
            with self.assertLogs("config.mail", level="ERROR"):
                deliver_verification_email(user.email_verification.pk)
        user.email_verification.refresh_from_db()
        self.assertIsNone(user.email_verification.sent_at)

        again = send_verification_email(user)
        self.assertTrue(again)
        self.assertEqual(again.reason, "queued")

    def test_successful_send_records_delivery(self):
        user = make_user()
        result = send_verification_email(user)
        self.assertEqual(result.reason, "queued")
        self.assertTrue(deliver_verification_email(user.email_verification.pk))
        user.email_verification.refresh_from_db()
        self.assertEqual(
            user.email_verification.email_status,
            EmailVerification.EmailStatus.SENT,
        )
        self.assertIsNotNone(user.email_verification.sent_at)

    def test_smtp_disconnect_marks_failed_and_never_sent(self):
        user = make_user()
        send_verification_email(user)
        with mock.patch(
            "config.mail._django_send_mail",
            side_effect=smtplib.SMTPServerDisconnected("connection lost"),
        ):
            with self.assertLogs("config.mail", level="ERROR") as logs:
                self.assertFalse(
                    deliver_verification_email(user.email_verification.pk)
                )

        record = EmailVerification.objects.get(user=user)
        self.assertEqual(record.email_status, EmailVerification.EmailStatus.FAILED)
        self.assertEqual(record.email_attempts, 1)
        self.assertIsNone(record.sent_at)
        self.assertTrue(record.email_last_error)
        self.assertTrue(
            any("SMTPServerDisconnected" in line for line in logs.output),
            logs.output,
        )

    def test_smtp_timeout_marks_failed_and_never_sent(self):
        user = make_user()
        send_verification_email(user)
        with mock.patch(
            "config.mail._django_send_mail",
            side_effect=TimeoutError("timed out"),
        ):
            with self.assertLogs("config.mail", level="ERROR"):
                self.assertFalse(
                    deliver_verification_email(user.email_verification.pk)
                )

        record = EmailVerification.objects.get(user=user)
        self.assertEqual(record.email_status, EmailVerification.EmailStatus.FAILED)
        self.assertEqual(record.email_attempts, 1)
        self.assertIsNone(record.sent_at)

    @override_settings(VERIFICATION_EMAIL_TIMEOUT=45)
    def test_delivery_uses_configured_timeout_for_slow_smtp_greeting(self):
        user = make_user()
        send_verification_email(user)
        with mock.patch("accounts.emails.send_mail", return_value=True) as send:
            self.assertTrue(
                deliver_verification_email(user.email_verification.pk)
            )

        self.assertEqual(send.call_args.kwargs["timeout"], 45)

    @override_settings(VERIFICATION_EMAIL_RETRY_AFTER_SECONDS=0)
    def test_retry_after_disconnect_marks_sent_only_when_accepted(self):
        user = make_user()
        send_verification_email(user)
        with mock.patch(
            "config.mail._django_send_mail",
            side_effect=smtplib.SMTPServerDisconnected("connection lost"),
        ):
            with self.assertLogs("config.mail", level="ERROR"):
                self.assertFalse(
                    deliver_verification_email(user.email_verification.pk)
                )

        record = EmailVerification.objects.get(user=user)
        self.assertEqual(record.email_status, EmailVerification.EmailStatus.FAILED)
        self.assertIsNone(record.sent_at)

        call_command("process_verification_emails", "--limit=10")
        record.refresh_from_db()
        self.assertEqual(record.email_status, EmailVerification.EmailStatus.SENT)
        self.assertIsNotNone(record.sent_at)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(VERIFICATION_EMAIL_RETRY_AFTER_SECONDS=0)
    def test_retry_command_retries_failed_email(self):
        user = make_user()
        send_verification_email(user)
        with self._break_smtp():
            with self.assertLogs("config.mail", level="ERROR"):
                deliver_verification_email(user.email_verification.pk)

        call_command("process_verification_emails", "--limit=10")
        user.email_verification.refresh_from_db()
        self.assertEqual(
            user.email_verification.email_status,
            EmailVerification.EmailStatus.SENT,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIsNotNone(user.email_verification.sent_at)

    @override_settings(
        VERIFICATION_EMAIL_RETRY_AFTER_SECONDS=0,
        VERIFICATION_EMAIL_MAX_ATTEMPTS=1,
    )
    def test_retry_command_respects_max_attempts(self):
        user = make_user()
        send_verification_email(user)
        record = user.email_verification
        record.email_status = EmailVerification.EmailStatus.FAILED
        record.email_attempts = 1
        record.email_last_attempt_at = timezone.now() - dt.timedelta(hours=1)
        record.save(
            update_fields=["email_status", "email_attempts", "email_last_attempt_at"]
        )

        call_command("process_verification_emails", "--limit=10")
        self.assertEqual(len(mail.outbox), 0)
        record.refresh_from_db()
        self.assertEqual(record.email_status, EmailVerification.EmailStatus.FAILED)

    @override_settings(VERIFICATION_EMAIL_STALE_SENDING_SECONDS=0)
    def test_retry_command_recovers_stale_sending_row(self):
        user = make_user()
        send_verification_email(user)
        record = user.email_verification
        record.email_status = EmailVerification.EmailStatus.SENDING
        record.email_attempts = 1
        record.email_last_attempt_at = timezone.now() - dt.timedelta(hours=1)
        record.save(
            update_fields=["email_status", "email_attempts", "email_last_attempt_at"]
        )

        call_command("process_verification_emails", "--limit=10")
        record.refresh_from_db()
        self.assertEqual(record.email_status, EmailVerification.EmailStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_logs_do_not_include_email_or_verification_link(self):
        user = make_user()
        url = verification_url(user)
        with self.assertLogs("accounts.emails", level="INFO") as logs:
            send_verification_email(user)
            with self._break_smtp():
                with self.assertLogs("config.mail", level="ERROR") as mail_logs:
                    deliver_verification_email(user.email_verification.pk)
        combined = "\n".join(logs.output + mail_logs.output)
        self.assertNotIn(user.email, combined)
        self.assertNotIn(url, combined)
        self.assertNotIn("password", combined.lower())


class RegistrationDeliveryFailureTests(TestCase):
    def test_failed_delivery_is_reported_and_account_is_kept(self):
        def fake_send(user, request=None):
            EmailVerification.objects.update_or_create(
                user=user,
                defaults={"email_status": EmailVerification.EmailStatus.FAILED},
            )
            return SendResult(True, "queued")

        with mock.patch(
            "accounts.views.send_verification_email", side_effect=fake_send
        ):
            response = self.client.post(
                reverse("accounts:register"),
                register_payload("retry@example.edu"),
            )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="retry@example.edu")
        self.assertFalse(email_is_verified(user))
        record = user.email_verification
        self.assertEqual(record.email_status, EmailVerification.EmailStatus.FAILED)
        messages = [str(message) for message in response.wsgi_request._messages]
        self.assertTrue(any("could not deliver" in message for message in messages), messages)


@override_settings(RATELIMIT_ENABLE=True)
class ResendRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_resend_verification_is_rate_limited(self):
        user = make_user()
        self.client.force_login(user)
        url = reverse("accounts:resend_verification")

        for _ in range(5):
            response = self.client.post(url)
            self.assertEqual(response.status_code, 302)

        response = self.client.post(url)
        self.assertEqual(response.status_code, 429)


class DefaultVerificationPolicyTests(TestCase):
    @override_settings(EMAIL_VERIFICATION_REQUIRED=False)
    def test_unverified_user_is_not_blocked_by_default(self):
        self.assertFalse(settings.EMAIL_VERIFICATION_REQUIRED)
        user = make_user()
        self.client.force_login(user)
        response = self.client.get(reverse("campus:dashboard"))
        self.assertNotEqual(
            response.get("Location", ""), reverse("accounts:verify_email_notice")
        )


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

    def test_notice_reflects_a_failed_delivery(self):
        user = make_user()
        EmailVerification.objects.create(
            user=user, email_status=EmailVerification.EmailStatus.FAILED
        )
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:verify_email_notice"))
        self.assertContains(response, "couldn't deliver")

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
