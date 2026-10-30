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
from django.utils import timezone

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


def _lock_pair(
    potential_match: PotentialMatch,
) -> tuple[PotentialMatch, PotentialMatch | None]:
    """Lock both proposal rows in ascending pk order.

    A stable lock order avoids a deadlock when two reviewers approve opposite
    halves of the same pair at the same time. The un-locked snapshot is only
    used to discover the reciprocal id; every field used for a decision is
    re-read after the locks are held.
    """

    snapshot = PotentialMatch.objects.select_related(
        "crush_entry", "registered_student"
    ).get(pk=potential_match.pk)
    partner_id = (
        PotentialMatch.objects.filter(
            crush_entry__submitted_by_id=snapshot.registered_student_id,
            registered_student_id=snapshot.crush_entry.submitted_by_id,
        )
        .exclude(pk=snapshot.pk)
        .values_list("pk", flat=True)
        .first()
    )
    ids = [snapshot.pk]
    if partner_id is not None:
        ids.append(partner_id)
    locked = {
        row.pk: row
        for row in PotentialMatch.objects.select_for_update()
        .select_related(
            "crush_entry",
            "crush_entry__submitted_by",
            "registered_student",
        )
        .filter(pk__in=ids)
        .order_by("pk")
    }
    return locked[snapshot.pk], locked.get(partner_id)


@transaction.atomic
def approve_potential_match(
    potential_match: PotentialMatch, admin_user, *, admin_notes: str = ""
) -> MutualMatch:
    """Turn a verified pending pair into a real, announced mutual crush.

    Refuses to act on anything that is not a reciprocal, still-eligible pending
    pair. Both rows and both entries are locked so an edit, block or concurrent
    reviewer cannot slip between validation and approval.
    """

    from .matching import compare

    primary, partner = _lock_pair(potential_match)
    if primary.status != PotentialMatch.Status.PENDING:
        raise ApprovalError("This proposal has already been reviewed.")
    if partner is None:
        raise ApprovalError(
            "The other student has not entered this person yet, so there is "
            "nothing to approve."
        )
    if partner.status != PotentialMatch.Status.PENDING:
        raise ApprovalError("The reciprocal half of this pair is no longer pending.")
    if primary.registered_student_id == primary.crush_entry.submitted_by_id:
        raise ApprovalError("A student cannot be their own crush.")

    author = primary.crush_entry.submitted_by
    candidate = primary.registered_student
    if author.college_id != candidate.college_id:
        raise ApprovalError("Crushes can never cross a campus boundary.")
    if not author.user.is_active or not candidate.user.is_active:
        raise ApprovalError("One of these accounts is no longer active.")
    if Block.objects.filter(
        Q(blocker=author, blocked=candidate) | Q(blocker=candidate, blocked=author)
    ).exists():
        raise ApprovalError("A block prevents this match from being approved.")

    # Read and lock the entries fresh. A stale linked object could hide an edit
    # that happened after the proposal was queued.
    entries = {
        entry.pk: entry
        for entry in CrushEntry.objects.select_for_update()
        .select_related("submitted_by")
        .filter(pk__in=[primary.crush_entry_id, partner.crush_entry_id])
    }
    entry_a = entries[primary.crush_entry_id]
    entry_b = entries[partner.crush_entry_id]
    if not entry_a.is_active or not entry_b.is_active:
        raise ApprovalError("One of these crush entries was removed.")
    if entry_a.submitted_by_id != author.pk or entry_b.submitted_by_id != candidate.pk:
        raise ApprovalError("The reciprocal entries no longer belong to this pair.")
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
    verdict_a = compare(entry_a, candidate)
    verdict_b = compare(entry_b, author)
    if not verdict_a.eligible or not verdict_b.eligible:
        blockers = "; ".join([*verdict_a.blockers, *verdict_b.blockers])
        raise ApprovalError(
            blockers or "The entries no longer pass the matching policy."
        )

    low, high = sorted([author.pk, candidate.pk])
    now = timezone.now()
    match = (
        MutualMatch.objects.select_for_update()
        .filter(user_a_id=low, user_b_id=high)
        .first()
    )
    if match is not None and match.status == MutualMatch.Status.CLOSED:
        raise ApprovalError("This pair was previously closed and cannot be reopened.")
    if match is None:
        try:
            with transaction.atomic():
                match = MutualMatch.objects.create(
                    user_a_id=low,
                    user_b_id=high,
                    status=MutualMatch.Status.MUTUAL,
                )
        except IntegrityError:
            # A concurrent approval won the unique-pair race.
            match = MutualMatch.objects.select_for_update().get(
                user_a_id=low, user_b_id=high
            )

    for row in (primary, partner):
        row.status = PotentialMatch.Status.APPROVED
        row.verified_at = now
        row.verified_by = admin_user
        row.mutual_match = match
        row.invalidated_reason = ""
        if admin_notes:
            row.admin_notes = admin_notes
        row.save(
            update_fields=[
                "status",
                "verified_at",
                "verified_by",
                "mutual_match",
                "invalidated_reason",
                "admin_notes",
            ]
        )

    # The conditional UPDATE is the at-most-once claim. It is intentionally not
    # conditional on ``created``: a reused open match that was never announced
    # must still produce its one notification.
    claimed = MutualMatch.objects.filter(
        pk=match.pk, notified_at__isnull=True
    ).update(notified_at=now)
    if claimed:
        notify_match(match)
        match.refresh_from_db()
    potential_match.refresh_from_db()
    return match


@transaction.atomic
def reject_potential_match(
    potential_match: PotentialMatch, admin_user, *, admin_notes: str = ""
) -> None:
    """Decline a proposal. The reciprocal half is rejected with it."""

    primary, partner = _lock_pair(potential_match)
    if primary.status != PotentialMatch.Status.PENDING:
        raise ApprovalError("This proposal has already been reviewed.")

    now = timezone.now()
    rows = [primary]
    if partner is not None and partner.status == PotentialMatch.Status.PENDING:
        rows.append(partner)

    for row in rows:
        row.status = PotentialMatch.Status.REJECTED
        row.verified_at = now
        row.verified_by = admin_user
        row.invalidated_reason = ""
        row.admin_notes = admin_notes or row.admin_notes
        row.save(
            update_fields=[
                "status",
                "verified_at",
                "verified_by",
                "invalidated_reason",
                "admin_notes",
            ]
        )
    potential_match.refresh_from_db()


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


def _email_available(student: StudentProfile) -> bool:
    return bool(
        getattr(settings, "MATCH_EMAILS_ENABLED", True)
        and student.user.email
    )


def _notification_for(
    *,
    student: StudentProfile,
    kind: str,
    message: str,
    url: str,
    dedupe_key: str,
    email_available: bool = False,
) -> tuple[Notification, bool]:
    defaults = {
        "student": student,
        "kind": kind,
        "message": message,
        "url": url,
        "email_status": (
            Notification.EmailStatus.PENDING
            if email_available
            else Notification.EmailStatus.SKIPPED
        ),
    }
    try:
        return Notification.objects.get_or_create(
            dedupe_key=dedupe_key, defaults=defaults
        )
    except IntegrityError:
        return Notification.objects.get(dedupe_key=dedupe_key), False


def _match_message(student: StudentProfile) -> str:
    site = getattr(settings, "SITE_URL", "")
    return MATCH_BODY.format(name=student.full_name.split(" ")[0], site=site)


def notify_match(match: MutualMatch) -> None:
    """Tell both sides it is mutual. Never mentions priority or the list.

    Notifications are deduplicated by ``(match, student)``. Email is queued
    through the Notification row and sent after the approval transaction
    commits, so a mail failure cannot roll back a valid match.
    """
    for student in (match.user_a, match.user_b):
        email_available = _email_available(student)
        notification, created = _notification_for(
            student=student,
            kind=Notification.Kind.MUTUAL,
            message="Someone you secretly selected also selected you.",
            url=match.get_absolute_url(),
            dedupe_key=f"mutual:{match.pk}:{student.pk}",
            email_available=email_available,
        )
        if created and email_available:
            transaction.on_commit(
                lambda notification_id=notification.pk: deliver_notification_email(
                    notification_id
                )
            )


def notify_reveal_pending(match: MutualMatch, student: StudentProfile) -> None:
    _notification_for(
        student=student,
        kind=Notification.Kind.REVEAL,
        message="Your mutual crush chose to reveal. Open to finish.",
        url=match.get_absolute_url(),
        dedupe_key=f"reveal:{match.pk}:{student.pk}",
        email_available=False,
    )


def deliver_notification_email(notification_id: int) -> bool:
    """Deliver one queued notification email with a visible outcome.

    The row is claimed as ``sending`` before the SMTP call, so two workers
    cannot send the same message. A failure is recorded and can be retried with
    ``manage.py retry_notifications``.
    """

    now = timezone.now()
    with transaction.atomic():
        notification = (
            Notification.objects.select_for_update()
            .select_related("student", "student__user")
            .filter(pk=notification_id)
            .first()
        )
        if notification is None:
            return False
        if notification.email_status in {
            Notification.EmailStatus.SENT,
            Notification.EmailStatus.SKIPPED,
        }:
            return False
        if notification.kind != Notification.Kind.MUTUAL:
            notification.email_status = Notification.EmailStatus.SKIPPED
            notification.save(update_fields=["email_status"])
            return False
        if not getattr(settings, "MATCH_EMAILS_ENABLED", True):
            notification.email_status = Notification.EmailStatus.SKIPPED
            notification.save(update_fields=["email_status"])
            return False
        email = notification.student.user.email
        if not email:
            notification.email_status = Notification.EmailStatus.SKIPPED
            notification.save(update_fields=["email_status"])
            return False
        notification.email_status = Notification.EmailStatus.SENDING
        notification.email_attempts += 1
        notification.email_last_attempt_at = now
        notification.email_last_error = ""
        notification.save(
            update_fields=[
                "email_status",
                "email_attempts",
                "email_last_attempt_at",
                "email_last_error",
            ]
        )
        subject = MATCH_SUBJECT
        body = _match_message(notification.student)

    ok = send_mail(subject, body, [email])
    with transaction.atomic():
        notification = Notification.objects.select_for_update().get(pk=notification_id)
        if ok:
            notification.email_status = Notification.EmailStatus.SENT
            notification.email_sent_at = timezone.now()
            notification.email_last_error = ""
        else:
            notification.email_status = Notification.EmailStatus.FAILED
            notification.email_last_error = "Mail server rejected or did not accept the message."
        notification.save(
            update_fields=[
                "email_status",
                "email_sent_at",
                "email_last_error",
            ]
        )
    return ok


def send_match_email(student: StudentProfile, match: MutualMatch | None = None) -> bool:
    """Send immediately, without the outbox.

    Retained for callers that explicitly want synchronous delivery. Normal
    approval uses :func:`deliver_notification_email` after commit instead.
    Never includes the counterpart's name, roll number, or priority.
    """
    if not getattr(settings, "MATCH_EMAILS_ENABLED", True):
        return False
    return send_mail(
        MATCH_SUBJECT,
        _match_message(student),
        [student.user.email],
    )