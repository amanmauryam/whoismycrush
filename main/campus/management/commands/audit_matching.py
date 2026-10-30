"""Read-only health report for identity resolution, matching and email."""

from django.core.management.base import BaseCommand
from django.db.models import Count

from campus.identity_resolution import IDENTITY_SCORING_VERSION
from campus.matching import MATCH_SCORING_VERSION
from campus.models import (
    CrushEntry,
    IdentityCandidate,
    MutualMatch,
    Notification,
    PotentialMatch,
)


class Command(BaseCommand):
    help = "Report stale proposals, legacy scores and email outbox health."

    def handle(self, *args, **options):
        entries = CrushEntry.objects.active()
        resolved = entries.exclude(resolved_student=None)
        legacy_entries = resolved.exclude(
            resolution_scoring_version=IDENTITY_SCORING_VERSION
        ).count()
        self.stdout.write(f"Active crush entries: {entries.count()}")
        self.stdout.write(f"Resolved crush entries: {resolved.count()}")
        self.stdout.write(f"Resolved with legacy/blank identity score: {legacy_entries}")

        pending = PotentialMatch.objects.filter(status=PotentialMatch.Status.PENDING)
        stale = PotentialMatch.objects.filter(status=PotentialMatch.Status.STALE)
        legacy_matches = (
            PotentialMatch.objects.exclude(scoring_version=MATCH_SCORING_VERSION)
            .exclude(status=PotentialMatch.Status.STALE)
            .count()
        )
        self.stdout.write(f"Pending proposals: {pending.count()}")
        self.stdout.write(f"Stale proposals: {stale.count()}")
        self.stdout.write(f"Live proposals with legacy scoring: {legacy_matches}")

        candidates = IdentityCandidate.objects.values("status").annotate(total=Count("id"))
        self.stdout.write("Identity candidates by status:")
        for row in candidates.order_by("status"):
            self.stdout.write(f"  {row['status']}: {row['total']}")
        legacy_candidates = IdentityCandidate.objects.exclude(
            scoring_version=IDENTITY_SCORING_VERSION
        ).count()
        self.stdout.write(f"Identity candidates with legacy scoring: {legacy_candidates}")

        unannounced = MutualMatch.objects.filter(notified_at__isnull=True).count()
        self.stdout.write(f"Mutual matches not yet announced: {unannounced}")

        emails = Notification.objects.values("email_status").annotate(total=Count("id"))
        self.stdout.write("Notification email outbox:")
        for row in emails.order_by("email_status"):
            self.stdout.write(f"  {row['email_status']}: {row['total']}")

        failed = Notification.objects.filter(
            email_status=Notification.EmailStatus.FAILED
        ).count()
        if failed:
            self.stdout.write(
                self.style.WARNING(
                    f"{failed} failed email(s). Run retry_notifications to retry."
                )
            )
