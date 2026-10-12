"""Sending and verifying the "confirm your email" link (requirements 3)."""

from __future__ import annotations

import datetime as dt

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from django.conf import settings

from .models import EmailVerification
from .tokens import email_verification_token

RESEND_COOLDOWN_SECONDS = getattr(settings, "VERIFICATION_RESEND_COOLDOWN_SECONDS", 60)

SUBJECT = "Confirm your email for WhoIsMyCrush"
BODY = """Hi {name},

Someone (hopefully you) started a private profile on WhoIsMyCrush with this
email address.

Confirm it here to finish setting up your campus ID:

{url}

The link is personal to you. If this wasn't you, you can ignore this email and
nothing will happen. Your crush list is private either way.

— WhoIsMyCrush
"""


def verification_url(user) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    path = reverse(
        "accounts:verify_email", kwargs={"uidb64": uid, "token": token}
    )
    return f"{settings.SITE_URL.rstrip('/')}{path}"


def check_verification_token(user, token) -> bool:
    if user is None or not token:
        return False
    return email_verification_token.check_token(user, token)


def send_verification_email(user, request=None) -> bool:
    """Send the link once. Returns False when throttled or already verified.

    ``request`` is accepted for symmetry with other mail helpers and future use
    (e.g. building an absolute URL from the host) but is not required.
    """
    record, _ = EmailVerification.objects.get_or_create(user=user)
    if record.verified_at is not None:
        return False

    now = _now()
    if record.sent_at and now - record.sent_at < dt.timedelta(seconds=RESEND_COOLDOWN_SECONDS):
        return False

    url = verification_url(user)
    send_mail(
        SUBJECT,
        BODY.format(name=(user.first_name or "there"), url=url),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=True,
    )
    record.sent_at = now
    record.save(update_fields=["sent_at"])
    return True


def mark_verified(user) -> bool:
    """Idempotently confirm an address. Returns True the first time only."""
    record, _ = EmailVerification.objects.get_or_create(user=user)
    if record.verified_at is not None:
        return False
    record.verified_at = _now()
    record.save(update_fields=["verified_at"])
    return True


def _now():
    from django.utils import timezone

    return timezone.now()
