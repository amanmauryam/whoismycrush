"""Safely re-resolve identities and refresh proposals after a policy change."""

from django.core.management.base import BaseCommand
from django.db import transaction

from campus.matching import propose_for_entry
from campus.models import CrushEntry


class Command(BaseCommand):
    help = "Re-run identity resolution and matching for active entries."

    def add_arguments(self, parser):
        parser.add_argument("--campus", type=int, help="Limit to one college id.")
        parser.add_argument("--limit", type=int, default=0, help="Max entries to process.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count what would be processed without writing.",
        )

    def handle(self, *args, **options):
        entries = (
            CrushEntry.objects.active()
            .select_related("submitted_by")
            .order_by("pk")
        )
        if options["campus"]:
            entries = entries.filter(college_id=options["campus"])
        if options["limit"]:
            entries = entries[: options["limit"]]

        total = entries.count() if hasattr(entries, "count") else len(entries)
        if options["dry_run"]:
            self.stdout.write(f"Would re-evaluate {total} active entries.")
            return

        processed = 0
        for entry in entries:
            with transaction.atomic():
                propose_for_entry(entry)
            processed += 1
            if processed % 100 == 0:
                self.stdout.write(f"Processed {processed} entries...")
        self.stdout.write(self.style.SUCCESS(f"Re-evaluated {processed} entries."))
