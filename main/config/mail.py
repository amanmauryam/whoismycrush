"""Observable email delivery, shared by every app that sends mail.

Historically each caller used ``django.core.mail.send_mail(..., fail_silently=True)``.
That made an SMTP outage completely invisible: the request still told the student
"we emailed you a confirmation link", the resend cooldown still advanced, and
nothing at all was written down. The only symptom was a registered user who
never received anything.

Every send now goes through :func:`send_mail`, which reports the outcome to the
caller and always logs a failure. Mail is best-effort -- a mail server outage
must never take down registration -- but it is never *silent*.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail as _django_send_mail

logger = logging.getLogger(__name__)


def send_mail(subject: str, message: str, recipients, *, from_email=None) -> bool:
    """Send one email. Returns ``True`` only if the server actually took it.

    ``recipients`` may be a single address or an iterable of them. Empty
    addresses are dropped. SMTP errors are caught, logged and reported as
    ``False`` rather than raised, so a broken mail server cannot break the
    request that triggered the mail.
    """
    if isinstance(recipients, str):
        recipients = [recipients]
    addresses = [address for address in (recipients or []) if address]
    if not addresses:
        logger.warning("Refusing to send %r: no recipients", subject)
        return False

    sender = from_email or settings.DEFAULT_FROM_EMAIL
    try:
        _django_send_mail(
            subject,
            message,
            sender,
            addresses,
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Could not send %r to %s (host=%s port=%s user=%s)",
            subject,
            ", ".join(addresses),
            getattr(settings, "EMAIL_HOST", ""),
            getattr(settings, "EMAIL_PORT", ""),
            getattr(settings, "EMAIL_HOST_USER", "") or "<none>",
        )
        return False
    return True
