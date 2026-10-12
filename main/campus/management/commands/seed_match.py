"""Create a real, admin-verified mutual crush between two demo students.

The product never lets a match exist without human verification
(requirements 10/14), so this command does not bypass the approval service.
It seeds two hand-typed entries, runs the matcher, then approves the resulting
reciprocal pair exactly as an admin would -- either as the ``--verifier`` you
name or as an existing superuser.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from campus.matching import match_entries_for, pending_pairs
from campus.models import CrushEntry, StudentProfile
from campus.services import ApprovalError, approve_potential_match

User = get_user_model()


def _entry(author, target, priority):
    entry, _ = CrushEntry.objects.get_or_create(
        submitted_by=author,
        priority=priority,
        defaults={
            "full_name": target.full_name,
            "roll_number": target.roll_number,
            "college": target.college,
            "course": target.course,
            "year": target.year,
            "section": target.section,
            "department": target.department,
            "nickname": target.nickname,
        },
    )
    return entry


class Command(BaseCommand):
    help = "Make two demo students enter each other and approve the match."

    def add_arguments(self, parser):
        parser.add_argument("--roll", default="23BCA104")
        parser.add_argument("--with-roll", dest="other_roll", default="23BCA107")
        parser.add_argument(
            "--verifier",
            default="",
            help="Username of a superuser to record as the approver.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        a = StudentProfile.objects.filter(roll_number__iexact=options["roll"]).first()
        b = StudentProfile.objects.filter(
            roll_number__iexact=options["other_roll"]
        ).first()

        if not a or not b:
            raise CommandError("Run `manage.py seed_demo` first.")

        _entry(a, b, 1)
        _entry(b, a, 2)
        match_entries_for(a)
        match_entries_for(b)

        pair = next(
            (
                row
                for row in pending_pairs()
                if a.pk in row["key"] and b.pk in row["key"]
            ),
            None,
        )
        if pair is None:
            raise CommandError(
                "No reciprocal pair was found. Both students must share a campus "
                "and their typed details must line up."
            )

        verifier = self._verifier(options["verifier"])
        try:
            match = approve_potential_match(pair["forward"], verifier)
        except ApprovalError as exc:
            raise CommandError(str(exc))

        self.stdout.write(
            self.style.SUCCESS(f"Approved mutual match #{match.pk} ({a.full_name} ♥ {b.full_name}).")
        )
        self.stdout.write(f"Open /matches/{match.pk}/")

    def _verifier(self, username):
        if username:
            user = User.objects.filter(username=username, is_superuser=True).first()
            if user is None:
                raise CommandError(f"No superuser named {username!r}.")
            return user
        user = User.objects.filter(is_superuser=True).order_by("pk").first()
        if user is None:
            raise CommandError(
                "Create a superuser first, or pass --verifier <username>."
            )
        return user
