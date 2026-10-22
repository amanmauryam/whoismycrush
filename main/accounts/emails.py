"""Sending and verifying the "confirm your email" link (requirements 3)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.conf import settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from config.mail import send_mail

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


@dataclass(frozen=True)
class SendResult:
    """Outcome of a verification email attempt.

    Truthy only when the mail really was handed to the server, so the existing
    ``if send_verification_email(user):`` style checks keep working while the
    views can still tell "throttled" apart from "failed".
    """

    sent: bool
    reason: str

    def __bool__(self) -> bool:
        return self.sent


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


def send_verification_email(user, request=None) -> SendResult:
    """Send the link once.

    Returns a :class:`SendResult` whose ``reason`` is one of:

    ``sent``
        The mail was accepted by the server.
    ``already_verified``
        The address is already confirmed, so no mail is needed.
    ``throttled``
        A link was sent moments ago; wait for the cooldown.
    ``failed``
        The server rejected the mail. Nothing was sent and the cooldown is
        *not* advanced, so the student can retry immediately.

    ``request`` is accepted for symmetry with other mail helpers and future use
    (e.g. building an absolute URL from the host) but is not required.
    """
    record, _ = EmailVerification.objects.get_or_create(user=user)
    if record.verified_at is not None:
        return SendResult(False, "already_verified")

    now = _now()
    if record.sent_at and now - record.sent_at < dt.timedelta(seconds=RESEND_COOLDOWN_SECONDS):
        return SendResult(False, "throttled")

    url = verification_url(user)
    recipient = (getattr(user, "email", "") or "").strip()
    if not recipient:
        username = (getattr(user, "username", "") or "").strip()
        if "@" in username:
            recipient = username
    if not recipient:
        # The cooldown exists to stop spamming, not to lock a student out after
        # a failed send. Leaving sent_at untouched lets them retry right away.
        return SendResult(False, "failed")

    delivered = send_mail(
        SUBJECT,
        BODY.format(name=(user.first_name or "there"), url=url),
        [recipient],
    )
    if not delivered:
        # The cooldown exists to stop spamming, not to lock a student out after
        # a failed send. Leaving sent_at untouched lets them retry right away.
        return SendResult(False, "failed")

    record.sent_at = now
    record.save(update_fields=["sent_at"])
    return SendResult(True, "sent")


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
