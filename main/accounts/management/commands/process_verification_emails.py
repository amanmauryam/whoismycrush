"""Deliver pending/failed verification emails from the durable outbox.

This is the crash-safe path. Run it from cron or a systemd timer, for example
every minute:

    * * * * * cd /srv/whoismycrush && python manage.py process_verification_emails

The post-commit dispatcher thread usually sends the message immediately; this
command recovers rows left behind by a restart, crash or SMTP outage.
"""

from __future__ import annotations

import datetime as dt

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from accounts.emails import deliver_verification_email
from accounts.models import EmailVerification


class Command(BaseCommand):
    help = "Retry pending/failed verification emails and recover stale sends."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many messages would be attempted.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        max_attempts = getattr(settings, "VERIFICATION_EMAIL_MAX_ATTEMPTS", 5)
        retry_after = getattr(settings, "VERIFICATION_EMAIL_RETRY_AFTER_SECONDS", 60)
        stale_after = getattr(
            settings, "VERIFICATION_EMAIL_STALE_SENDING_SECONDS", 300
        )
        retry_before = now - dt.timedelta(seconds=retry_after)
        stale_before = now - dt.timedelta(seconds=stale_after)

        eligible = (
            Q(
                email_status=EmailVerification.EmailStatus.PENDING,
                email_attempts__lt=max_attempts,
            )
            | Q(
                email_status=EmailVerification.EmailStatus.FAILED,
                email_attempts__lt=max_attempts,
            )
            & (
                Q(email_last_attempt_at__isnull=True)
                | Q(email_last_attempt_at__lte=retry_before)
            )
            | Q(
                email_status=EmailVerification.EmailStatus.SENDING,
            )
            & (
                Q(email_last_attempt_at__isnull=True)
                | Q(email_last_attempt_at__lte=stale_before)
            )
        )

        candidates = (
            EmailVerification.objects.filter(
                verified_at__isnull=True,
            )
            .filter(eligible)
            .order_by("email_queued_at", "created_at")[: options["limit"]]
        )

        if options["dry_run"]:
            self.stdout.write(f"Would attempt {candidates.count()} email(s).")
            return

        sent = failed = 0
        for record in candidates:
            if deliver_verification_email(record.pk, retry_stale=True):
                sent += 1
            else:
                failed += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {sent} verification email(s); {failed} failed or skipped."
            )
        )
