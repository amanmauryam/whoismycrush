"""Observable email delivery, shared by every app that sends mail.

Every send goes through :func:`send_mail`, which reports the outcome to the
caller and always logs a failure. Mail is best-effort -- a mail server outage
must never take down registration -- but it is never *silent*.

Logs deliberately contain no recipient addresses, usernames, passwords or
message bodies, because those can identify students and message bodies may
contain verification links.
"""

from __future__ import annotations

import logging
import time

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail import send_mail as _django_send_mail

logger = logging.getLogger(__name__)


def _smtp_code(exc: Exception):
    return getattr(exc, "smtp_code", None)


def send_mail(
    subject: str,
    message: str,
    recipients,
    *,
    from_email=None,
    timeout=None,
) -> bool:
    """Send one email. Returns ``True`` only if the server actually took it.

    ``recipients`` may be a single address or an iterable of them. Empty
    addresses are dropped. SMTP errors are caught, logged and reported as
    ``False`` rather than raised, so a broken mail server cannot break the
    request that triggered the mail. ``timeout`` overrides Django's configured
    SMTP timeout for this send.
    """

    started = time.perf_counter()
    if isinstance(recipients, str):
        recipients = [recipients]
    addresses = [address for address in (recipients or []) if address]
    if not addresses:
        logger.warning("Refusing to send %r: no recipients", subject)
        return False

    sender = from_email or settings.DEFAULT_FROM_EMAIL
    connection = get_connection(timeout=timeout) if timeout is not None else None
    try:
        _django_send_mail(
            subject,
            message,
            sender,
            addresses,
            fail_silently=False,
            connection=connection,
        )
    except Exception as exc:
        logger.error(
            "Could not send %r (recipients=%d, host=%s port=%s, error=%s, smtp_code=%s)",
            subject,
            len(addresses),
            getattr(settings, "EMAIL_HOST", ""),
            getattr(settings, "EMAIL_PORT", ""),
            type(exc).__name__,
            _smtp_code(exc) or "-",
        )
        logger.info(
            "smtp_timing elapsed_ms=%.2f result=error",
            (time.perf_counter() - started) * 1000,
        )
        return False
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    logger.info(
        "smtp_timing elapsed_ms=%.2f result=ok",
        (time.perf_counter() - started) * 1000,
    )
    return True
