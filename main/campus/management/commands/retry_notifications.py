"""Retry queued or failed match emails from the notification outbox."""

from django.conf import settings
from django.core.management.base import BaseCommand

from campus.models import Notification
from campus.services import deliver_notification_email


class Command(BaseCommand):
    help = "Retry pending or failed match emails."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many messages would be attempted.",
        )
        parser.add_argument(
            "--include-pending",
            action="store_true",
            help="Also retry messages still marked pending.",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "MATCH_EMAILS_ENABLED", True):
            self.stdout.write("MATCH_EMAILS_ENABLED is off; nothing to do.")
            return
        statuses = [Notification.EmailStatus.FAILED]
        if options["include_pending"]:
            statuses.append(Notification.EmailStatus.PENDING)
        candidates = Notification.objects.filter(
            email_status__in=statuses,
            email_attempts__lt=getattr(settings, "NOTIFICATION_EMAIL_MAX_ATTEMPTS", 5),
        ).order_by("created_at")[: options["limit"]]

        if options["dry_run"]:
            self.stdout.write(f"Would attempt {candidates.count()} email(s).")
            return

        sent = failed = 0
        for notification in candidates:
            if deliver_notification_email(notification.pk):
                sent += 1
            else:
                failed += 1
        self.stdout.write(
            self.style.SUCCESS(f"Sent {sent} email(s); {failed} failed or skipped.")
        )
