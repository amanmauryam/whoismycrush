"""Matching engine, sealing, and the admin-gated notification path.

The invariant this whole module exists to protect: **neither student is ever
told anything until an admin approves a pending pair** (requirements 10/14/15/17).

Sealing a list is silent. It just freezes what the student typed and asks the
matcher to look for registered students whose identity lines up. Any hit becomes
a ``PotentialMatch`` in ``pending`` status. Only :func:`approve_potential_match`
can turn that into a real ``MutualMatch`` and notify anyone, and both the admin
detail view and the Django admin action call that one function (requirements
14/24).
"""

from __future__ import annotations

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q

from config.mail import send_mail

from .models import (
    MAX_CRUSHES,
    Block,
    CrushEntry,
    MutualMatch,
    Notification,
    PotentialMatch,
    StudentProfile,
)

MATCH_SUBJECT = "Someone might be your mutual crush 👀"
MATCH_BODY = """Hi {name},

Someone you secretly selected also secretly selected you.

Our team checked both sides carefully, and this one is confirmed mutual.

Your secret is still safe. Nobody can see your list, your priorities, or who
else you picked.

Open {site} to see what happened.

— WhoIsMyCrush
"""


class SelectionError(Exception):
    """Raised when a submission violates a product rule."""

    def __init__(self, message: str, code: str = "invalid"):
        super().__init__(message)
        self.code = code


class ApprovalError(Exception):
    """Raised when an admin action cannot be carried out."""


# ---------------------------------------------------------------------------
# Sealing
# ---------------------------------------------------------------------------


@transaction.atomic
def seal_secret(student: StudentProfile) -> int:
    """Freeze the current list and queue any reciprocal pairs for review.

    Returns the number of *pending proposals* discovered. Nothing is confirmed
    and nobody is notified here -- that only happens on admin approval
    (requirements 6/10/17/22/26).

    Sealing twice is harmless: proposals are deduplicated on
    ``(crush_entry, registered_student)``.
    """
    from . import matching  # local import: matching imports models

    entries = list(
        CrushEntry.objects.active()
        .select_for_update()
        .filter(submitted_by=student)
        .order_by("priority", "created_at")
    )
    if not entries:
        raise SelectionError("Add at least one crush before sealing.", code="empty")
    if len(entries) > MAX_CRUSHES:
        raise SelectionError(f"You can only enter {MAX_CRUSHES} people.", code="overflow")

    proposals = matching.match_entries_for(student)
    return len(proposals)


# ---------------------------------------------------------------------------
# Admin-gated approval (the only path to a MutualMatch)
# ---------------------------------------------------------------------------


@transaction.atomic
def approve_potential_match(
    potential_match: PotentialMatch, admin_user, *, admin_notes: str = ""
) -> MutualMatch:
    """Turn a verified pending pair into a real, announced mutual crush.

    Refuses to act on anything that is not a reciprocal, pending pair, and is
    idempotent per pair so the same mutual can never be created or announced
    twice (requirements 14/18).
    """
    potential_match.refresh_from_db()
    if potential_match.status != PotentialMatch.Status.PENDING:
        raise ApprovalError("This proposal has already been reviewed.")
    if potential_match.registered_student_id == potential_match.author.pk:
        raise ApprovalError("A student cannot be their own crush.")

    partner = potential_match.reciprocal
    if partner is None:
        raise ApprovalError(
            "The other student has not entered this person yet, so there is "
            "nothing to approve."
        )
    partner.refresh_from_db()
    if partner.status == PotentialMatch.Status.REJECTED:
        raise ApprovalError("The reciprocal half of this pair was already rejected.")

    author = potential_match.author
    candidate = potential_match.registered_student
    if author.college_id != candidate.college_id:
        raise ApprovalError("Crushes can never cross a campus boundary.")
    if not author.user.is_active or not candidate.user.is_active:
        raise ApprovalError("One of these accounts is no longer active.")
    if Block.objects.filter(
        Q(blocker=author, blocked=candidate) | Q(blocker=candidate, blocked=author)
    ).exists():
        raise ApprovalError("A block prevents this match from being approved.")

    # Only correctly resolved reciprocal identities may become a match. This
    # catches an entry edited after the proposal was queued. Read the entries
    # fresh rather than trusting a cached related object.
    entry_a = CrushEntry.objects.get(pk=potential_match.crush_entry_id)
    entry_b = CrushEntry.objects.get(pk=partner.crush_entry_id)
    if entry_a.resolved_student_id != candidate.pk:
        raise ApprovalError(
            "Person A's entry is no longer verified as pointing at Person B. "
            "Resolve the identity again before approving."
        )
    if entry_b.resolved_student_id != author.pk:
        raise ApprovalError(
            "Person B's entry is no longer verified as pointing at Person A. "
            "Resolve the identity again before approving."
        )

    now = _now()
    with transaction.atomic():
        try:
            with transaction.atomic():
                match, created = MutualMatch.objects.get_or_create(
                    user_a_id=min(author.pk, candidate.pk),
                    user_b_id=max(author.pk, candidate.pk),
                    defaults={"status": MutualMatch.Status.MUTUAL},
                )
        except IntegrityError:
            # A concurrent approval won the unique-pair race.
            match = MutualMatch.objects.get(
                user_a_id=min(author.pk, candidate.pk),
                user_b_id=max(author.pk, candidate.pk),
            )
            created = False

        for row in (potential_match, partner):
            row.status = PotentialMatch.Status.APPROVED
            row.verified_at = now
            row.verified_by = admin_user
            row.mutual_match = match
            if admin_notes:
                row.admin_notes = admin_notes
            row.save(
                update_fields=[
                    "status",
                    "verified_at",
                    "verified_by",
                    "mutual_match",
                    "admin_notes",
                ]
            )

        # Announce only now, once, and only when this approval is what created
        # the match. The conditional UPDATE is the at-most-once claim: two
        # concurrent approvers cannot both send the same notification.
        if created:
            claimed = MutualMatch.objects.filter(
                pk=match.pk, notified_at__isnull=True
            ).update(notified_at=now)
            if claimed:
                notify_match(match)
                match.refresh_from_db()
    return match


@transaction.atomic
def reject_potential_match(
    potential_match: PotentialMatch, admin_user, *, admin_notes: str = ""
) -> None:
    """Decline a proposal. The reciprocal half is rejected with it.

    Rejecting closes the pair permanently: the matcher will not recreate the
    proposal, because proposals are only ever created with ``get_or_create``.
    """
    if potential_match.status != PotentialMatch.Status.PENDING:
        raise ApprovalError("This proposal has already been reviewed.")

    now = _now()
    rows = [potential_match]
    partner = potential_match.reciprocal
    if partner is not None and partner.status == PotentialMatch.Status.PENDING:
        rows.append(partner)

    for row in rows:
        row.status = PotentialMatch.Status.REJECTED
        row.verified_at = now
        row.verified_by = admin_user
        row.admin_notes = admin_notes or row.admin_notes
        row.save(
            update_fields=["status", "verified_at", "verified_by", "admin_notes"]
        )


def _now():
    from django.utils import timezone

    return timezone.now()


# ---------------------------------------------------------------------------
# Backstop sweeps (maintenance / re-runs)
# ---------------------------------------------------------------------------


def reconcile_all_matches() -> int:
    """Re-run the matcher across every active entry and report new proposals."""
    from . import matching

    created = []
    entries = CrushEntry.objects.active().select_related("college").order_by("pk")
    for entry in entries.iterator():
        created.extend(matching.propose_for_entry(entry))
    return len(created)


def prune_broken_matches() -> int:
    """Drop matches whose reciprocal halves were rejected or removed."""
    stale = []
    for match in MutualMatch.objects.select_related("user_a", "user_b").all():
        low, high = sorted([match.user_a_id, match.user_b_id])
        approved = PotentialMatch.objects.filter(
            status=PotentialMatch.Status.APPROVED,
            mutual_match=match,
        ).exists()
        if approved:
            continue
        rejected = PotentialMatch.objects.filter(
            status=PotentialMatch.Status.REJECTED,
            crush_entry__submitted_by_id=low,
            registered_student_id=high,
        ).exists()
        if rejected:
            stale.append(match.pk)
    if stale:
        MutualMatch.objects.filter(pk__in=stale).delete()
    return len(stale)


# ---------------------------------------------------------------------------
# Campus statistics (aggregate only, never identities -- design.md 23)
# ---------------------------------------------------------------------------


def campus_status(student: StudentProfile) -> dict:
    from .forms import active_entry_count

    college = student.college
    return {
        "students": StudentProfile.objects.filter(college=college).count(),
        "matches": MutualMatch.objects.filter(
            Q(user_a__college=college) | Q(user_b__college=college)
        ).count(),
        "your_matches": MutualMatch.objects.for_student(student).count(),
        "sealed": active_entry_count(student),
    }


# ---------------------------------------------------------------------------
# Notifications (only ever fired post-approval -- requirements 15/17)
# ---------------------------------------------------------------------------


def notify_match(match: MutualMatch) -> None:
    """Tell both sides it is mutual. Never mentions priority or the list."""
    for student in (match.user_a, match.user_b):
        Notification.objects.create(
            student=student,
            kind=Notification.Kind.MUTUAL,
            message="Someone you secretly selected also selected you.",
            url=match.get_absolute_url(),
        )
        send_match_email(student, match)


def notify_reveal_pending(match: MutualMatch, student: StudentProfile) -> None:
    Notification.objects.create(
        student=student,
        kind=Notification.Kind.REVEAL,
        message="Your mutual crush chose to reveal. Open to finish.",
        url=match.get_absolute_url(),
    )


def send_match_email(student: StudentProfile, match: MutualMatch | None = None) -> bool:
    """Never includes the counterpart's name, roll number, or priority.

    Returns ``True`` only if the mail was accepted by the server. The in-app
    ``Notification`` is written regardless, so a mail outage never hides the
    match from the student.
    """
    site = getattr(settings, "SITE_URL", "")
    if not getattr(settings, "MATCH_EMAILS_ENABLED", True):
        return False
    return send_mail(
        MATCH_SUBJECT,
        MATCH_BODY.format(name=student.full_name.split(" ")[0], site=site),
        [student.user.email],
    )