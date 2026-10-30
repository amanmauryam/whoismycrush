"""Sending and verifying the "confirm your email" link (requirements 3).

Verification mail goes through the ``EmailVerification`` row as a durable
outbox. Registration/resend only writes a ``PENDING`` row and returns; a
best-effort dispatcher thread tries immediately, while
``manage.py process_verification_emails`` is the crash-safe retry path.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
import logging
import threading
import time

from django.conf import settings
from django.db import OperationalError, close_old_connections, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from config.mail import send_mail

from .models import EmailVerification
from .tokens import email_verification_token

logger = logging.getLogger(__name__)

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
    """Outcome of a verification email request.

    Truthy when the message was accepted into the durable outbox (``queued``)
    or was already queued. It deliberately does **not** mean SMTP accepted the
    message; delivery is recorded separately on the outbox row.
    """

    sent: bool
    reason: str

    def __bool__(self) -> bool:
        return self.sent


def _now():
    return timezone.now()


def _cooldown_seconds() -> int:
    return getattr(settings, "VERIFICATION_RESEND_COOLDOWN_SECONDS", 60)


def _max_attempts() -> int:
    return getattr(settings, "VERIFICATION_EMAIL_MAX_ATTEMPTS", 5)


def _timeout_seconds() -> int:
    timeout = getattr(settings, "VERIFICATION_EMAIL_TIMEOUT", 45)
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        return 45
    return timeout if timeout > 0 else 45


def _stale_sending_seconds() -> int:
    return getattr(settings, "VERIFICATION_EMAIL_STALE_SENDING_SECONDS", 300)


def _retry_after_seconds() -> int:
    return getattr(settings, "VERIFICATION_EMAIL_RETRY_AFTER_SECONDS", 60)


def _recipient_for(user) -> str:
    recipient = (getattr(user, "email", "") or "").strip()
    if recipient:
        return recipient
    username = (getattr(user, "username", "") or "").strip()
    return username if "@" in username else ""


def _clear_cached_record(user) -> None:
    """Drop a stale reverse one-to-one cache after the outbox row changes."""

    cache = getattr(getattr(user, "_state", None), "fields_cache", None)
    if cache is not None:
        cache.pop("email_verification", None)


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
    """Queue the confirmation link once and return without waiting for SMTP.

    ``request`` is accepted for symmetry with other mail helpers and future use
    (e.g. building an absolute URL from the host) but is not required.

    Reasons are ``queued``, ``already_queued``, ``already_verified``,
    ``throttled`` and ``failed``. A queued result is not a delivery receipt.
    """

    started = time.perf_counter()
    verification_id = None
    should_dispatch = False
    already_queued = False

    with transaction.atomic():
        record, _ = EmailVerification.objects.get_or_create(user=user)
        _clear_cached_record(user)
        record = EmailVerification.objects.select_for_update().get(pk=record.pk)

        if record.verified_at is not None:
            return SendResult(False, "already_verified")

        now = _now()
        if record.sent_at and now - record.sent_at < dt.timedelta(
            seconds=_cooldown_seconds()
        ):
            return SendResult(False, "throttled")

        if record.email_status in {
            EmailVerification.EmailStatus.PENDING,
            EmailVerification.EmailStatus.SENDING,
        }:
            # Do not queue a duplicate. Re-submitting the dispatcher is safe:
            # delivery claims the row atomically, so only one worker sends it.
            verification_id = record.pk
            should_dispatch = True
            already_queued = True
        else:
            recipient = _recipient_for(user)
            if not recipient:
                # The cooldown exists to stop spamming, not to lock a student
                # out after a failed send. Leaving sent_at untouched lets them
                # retry as soon as they fix their address.
                return SendResult(False, "failed")

            record.email_status = EmailVerification.EmailStatus.PENDING
            record.email_attempts = 0
            record.email_last_error = ""
            record.email_queued_at = now
            record.email_last_attempt_at = None
            record.save(
                update_fields=[
                    "email_status",
                    "email_attempts",
                    "email_last_error",
                    "email_queued_at",
                    "email_last_attempt_at",
                ]
            )
            verification_id = record.pk
            should_dispatch = True

    if should_dispatch and verification_id is not None:
        transaction.on_commit(
            lambda verification_id=verification_id: _submit_verification_email(
                verification_id
            )
        )

    logger.info(
        "verification_email_queued verification_id=%s elapsed_ms=%.2f",
        verification_id,
        (time.perf_counter() - started) * 1000,
    )
    reason = "already_queued" if already_queued else "queued"
    return SendResult(True, reason)


def _submit_verification_email(verification_id: int) -> None:
    """Start a best-effort dispatcher; the outbox row is the source of truth."""

    if not getattr(settings, "VERIFICATION_EMAIL_ASYNC", True):
        _deliver_safely(verification_id)
        return

    try:
        thread = threading.Thread(
            target=_deliver_safely,
            args=(verification_id,),
            name=f"verification-email-{verification_id}",
            daemon=True,
        )
        thread.start()
    except Exception as exc:
        # The row stays PENDING and the retry command will pick it up.
        logger.error(
            "verification_email_dispatch_unavailable verification_id=%s error=%s",
            verification_id,
            type(exc).__name__,
        )


def _deliver_safely(verification_id: int) -> None:
    close_old_connections()
    try:
        # Give the request a moment to finish its session write. SQLite only
        # allows one writer, and the outbox row is already safely committed.
        time.sleep(0.1)
        for attempt in range(3):
            try:
                deliver_verification_email(verification_id)
                return
            except OperationalError as exc:
                if attempt == 2:
                    # The row stays pending/sending; the cron command recovers it.
                    logger.warning(
                        "verification_email_dispatch_deferred verification_id=%s error=%s",
                        verification_id,
                        type(exc).__name__,
                    )
                    return
                time.sleep(0.5 * (attempt + 1))
                close_old_connections()
    except Exception as exc:
        logger.error(
            "verification_email_dispatch_failed verification_id=%s error=%s",
            verification_id,
            type(exc).__name__,
        )
        _mark_unexpected_failure(verification_id)
    finally:
        close_old_connections()


def _mark_unexpected_failure(verification_id: int) -> None:
    EmailVerification.objects.filter(
        pk=verification_id,
        email_status=EmailVerification.EmailStatus.SENDING,
    ).update(
        email_status=EmailVerification.EmailStatus.FAILED,
        email_last_error="Unexpected delivery error.",
    )


def deliver_verification_email(verification_id: int, *, retry_stale: bool = False) -> bool:
    """Deliver one queued verification email with a visible outcome.

    The row is claimed as ``sending`` before the SMTP call, so two workers
    cannot send the same message at the same time. Failures are recorded for
    ``manage.py process_verification_emails``. A crash between SMTP accepting
    the message and the final database update can cause an at-least-once
    duplicate; the row remains recoverable instead of being lost.
    """

    now = _now()
    with transaction.atomic():
        record = (
            EmailVerification.objects.select_for_update()
            .select_related("user")
            .filter(pk=verification_id)
            .first()
        )
        if record is None:
            return False
        if record.verified_at is not None:
            if record.email_status != EmailVerification.EmailStatus.SKIPPED:
                record.email_status = EmailVerification.EmailStatus.SKIPPED
                record.save(update_fields=["email_status"])
            return False
        if record.email_status in {
            EmailVerification.EmailStatus.SENT,
            EmailVerification.EmailStatus.SKIPPED,
        }:
            return False
        if record.email_status == EmailVerification.EmailStatus.SENDING:
            last_attempt = record.email_last_attempt_at
            if not retry_stale or (
                last_attempt is not None
                and now - last_attempt < dt.timedelta(seconds=_stale_sending_seconds())
            ):
                return False
        elif record.email_attempts >= _max_attempts():
            return False

        recipient = _recipient_for(record.user)
        if not recipient:
            record.email_status = EmailVerification.EmailStatus.SKIPPED
            record.email_last_error = "No recipient address."
            record.save(update_fields=["email_status", "email_last_error"])
            return False

        subject = SUBJECT
        body = BODY.format(
            name=(record.user.first_name or "there"),
            url=verification_url(record.user),
        )
        record.email_status = EmailVerification.EmailStatus.SENDING
        record.email_attempts += 1
        record.email_last_attempt_at = now
        record.email_last_error = ""
        record.save(
            update_fields=[
                "email_status",
                "email_attempts",
                "email_last_attempt_at",
                "email_last_error",
            ]
        )
        attempts = record.email_attempts

    ok = send_mail(subject, body, [recipient], timeout=_timeout_seconds())

    with transaction.atomic():
        record = EmailVerification.objects.select_for_update().get(pk=verification_id)
        if ok:
            record.email_status = EmailVerification.EmailStatus.SENT
            record.sent_at = _now()
            record.email_last_error = ""
        else:
            record.email_status = EmailVerification.EmailStatus.FAILED
            record.email_last_error = (
                "Mail server rejected or did not accept the message."
            )
        record.save(
            update_fields=["email_status", "sent_at", "email_last_error"]
        )

    logger.info(
        "verification_email_delivery verification_id=%s status=%s attempts=%s",
        verification_id,
        record.email_status,
        attempts,
    )
    return ok


def mark_verified(user) -> bool:
    """Idempotently confirm an address. Returns True the first time only."""
    record, _ = EmailVerification.objects.get_or_create(user=user)
    if record.verified_at is not None:
        return False
    record.verified_at = _now()
    record.email_status = EmailVerification.EmailStatus.SKIPPED
    record.email_last_error = ""
    record.save(
        update_fields=["verified_at", "email_status", "email_last_error"]
    )
    return True
