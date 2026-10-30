"""Identity resolution for hand-typed crush entries.

This module answers one question only: *is there enough evidence to link a
typed ``CrushEntry`` to a registered ``StudentProfile``?* It deliberately does
not create matches or notify anyone. Match proposals remain a separate,
admin-gated concern in :mod:`campus.matching` and :mod:`campus.services`.

Design rules
------------
* College scope is always applied first. Expensive name comparison never runs
  across the whole student table.
* An exact roll number alone is not proof of identity; a name similarity alone
  is even weaker. Auto-resolution therefore requires an exact campus + roll
  match *and* a close name, with no contradicting course/year/section.
* Missing or conflicting roll numbers produce review candidates, never an
  automatic link. The submitted entry is always preserved.
* Rejected or deferred candidates are sticky: reprocessing cannot silently
  re-bind them.
* Every resolution decision writes :class:`IdentityResolutionAudit` with ids
  only, never the typed name or roll.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from . import policy
from .matching import name_similarity, normalize_text
from .models import (
    Block,
    CrushEntry,
    IdentityCandidate,
    IdentityResolutionAudit,
    PotentialMatch,
    StudentProfile,
)

logger = logging.getLogger(__name__)

IDENTITY_SCORING_VERSION = "identity-v2"

# Explainable identity weights. They sum to 100 when every attribute matches.
W_ROLL = 45.0
W_NAME = 30.0
W_NICKNAME = 5.0
W_COURSE = 8.0
W_YEAR = 5.0
W_SECTION = 4.0
W_DEPARTMENT = 3.0

#: Human-readable labels and maximum points for the review-desk breakdown.
IDENTITY_COMPONENT_LABELS = {
    "roll": ("Roll number", W_ROLL),
    "name": ("Name similarity", W_NAME),
    "nickname": ("Nickname", W_NICKNAME),
    "course": ("Course", W_COURSE),
    "year": ("Year", W_YEAR),
    "section": ("Section", W_SECTION),
    "department": ("Department", W_DEPARTMENT),
}

#: Name score buckets. Exact names are the only name signal strong enough to
#: contribute meaningfully on its own; variants get partial credit so a human
#: can still review them.
_NAME_POINTS = (
    (0.999, W_NAME),
    (0.92, W_NAME * 0.90),
    (0.82, W_NAME * 0.72),
    (0.70, W_NAME * 0.50),
    (0.62, W_NAME * 0.28),
)


class IdentityResolutionError(ValueError):
    """Raised when an identity operation would create an unsafe binding."""


@dataclass
class ScoredCandidate:
    student: StudentProfile
    score: float
    name_similarity: float
    reasons: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    roll_exact: bool = False
    roll_conflict: bool = False
    auto_resolvable: bool = False
    components: dict[str, float] = field(default_factory=dict)

    @property
    def hard_conflict(self) -> bool:
        # Roll number conflict is a hard conflict
        if self.roll_conflict:
            return True
        # Check if any conflict is in hard fields per policy
        if self.conflicts:
            return True
        return False

    @property
    def evidence(self) -> dict:
        return {
            "roll_exact": self.roll_exact,
            "roll_conflict": self.roll_conflict,
            "name_similarity": round(self.name_similarity, 3),
            "reasons": list(self.reasons),
            "conflicts": list(self.conflicts),
            "score": self.score,
            "components": {
                key: round(float(value), 2) for key, value in self.components.items()
            },
        }


def _setting(name: str, default):
    return getattr(settings, name, default)


def _candidate_min_score() -> float:
    return float(_setting("IDENTITY_CANDIDATE_MIN_SCORE", 50.0))


def _name_candidate_min() -> float:
    return float(_setting("IDENTITY_NAME_CANDIDATE_MIN", 0.70))


def _auto_name_min() -> float:
    return float(_setting("IDENTITY_AUTO_RESOLVE_MIN_NAME_SIMILARITY", 0.88))


def _auto_enabled() -> bool:
    return bool(_setting("IDENTITY_AUTO_RESOLVE_ENABLED", True))


def _fuzzy_limit() -> int:
    return int(_setting("IDENTITY_FUZZY_SCAN_LIMIT", 500))


def _max_candidates() -> int:
    return int(_setting("IDENTITY_MAX_CANDIDATES", 10))


def _require_verified_for_auto() -> bool:
    return bool(_setting("IDENTITY_REQUIRE_STUDENT_VERIFICATION_FOR_AUTO", False))


def _blocked_ids(student: StudentProfile) -> set[int]:
    outgoing = Block.objects.filter(blocker=student).values_list("blocked_id", flat=True)
    incoming = Block.objects.filter(blocked=student).values_list("blocker_id", flat=True)
    return {*outgoing, *incoming}


def _active_students() -> "Q":
    return Q(user__is_active=True)


def _name_scope(entry: CrushEntry) -> Q:
    """Cheap, college-scoped prefilter for fuzzy name exploration.

    Each typed token contributes its first character. That catches Niki/Nikki,
    Riya/Rhea and surname-first ordering without comparing every student in the
    campus. The result is capped by ``IDENTITY_FUZZY_SCAN_LIMIT``.
    """

    scope = Q()
    for token in set(entry.normalized_name.split()):
        if not token:
            continue
        first = token[0]
        scope |= Q(normalized_name__startswith=first) | Q(
            normalized_name__contains=f" {first}"
        )
    return scope


def candidate_pool(entry: CrushEntry, *, limit: int | None = None) -> list[StudentProfile]:
    """Return a bounded, college-scoped pool of possible registered students."""

    limit = limit or _fuzzy_limit()
    base = (
        StudentProfile.objects.filter(college_id=entry.college_id)
        .filter(_active_students())
        .exclude(pk=entry.submitted_by_id)
    )
    blocked = _blocked_ids(entry.submitted_by)
    if blocked:
        base = base.exclude(pk__in=blocked)

    found: dict[int, StudentProfile] = {}

    def add(queryset, cap=None):
        rows = queryset.order_by("pk")
        if cap:
            rows = rows[:cap]
        for student in rows:
            found.setdefault(student.pk, student)

    if entry.normalized_roll_number:
        add(base.filter(normalized_roll_number=entry.normalized_roll_number), cap=20)
    if entry.normalized_name:
        add(base.filter(normalized_name=entry.normalized_name), cap=50)
        add(base.filter(_name_scope(entry)), cap=limit)
    if entry.nickname:
        add(base.filter(nickname__iexact=entry.nickname), cap=20)

    return list(found.values())


def score_candidate(entry: CrushEntry, student: StudentProfile) -> ScoredCandidate:
    """Score one possible identity with explainable, human-readable evidence."""

    reasons: list[str] = []
    conflicts: list[str] = []
    score = 0.0
    components: dict[str, float] = {}
    hard_fields = policy.identity_hard_fields()

    if entry.college_id != student.college_id:
        return ScoredCandidate(student, 0.0, 0.0, conflicts=["different campus"])

    if entry.submitted_by_id == student.pk:
        return ScoredCandidate(student, 0.0, 0.0, conflicts=["same student"])

    if not student.user.is_active:
        return ScoredCandidate(student, 0.0, 0.0, conflicts=["inactive account"])

    # -- roll number ------------------------------------------------------
    roll_exact = bool(
        entry.normalized_roll_number
        and entry.normalized_roll_number == student.normalized_roll_number
    )
    roll_conflict = bool(entry.normalized_roll_number and not roll_exact)
    components["roll"] = 0.0
    if roll_exact:
        score += W_ROLL
        components["roll"] = W_ROLL
        reasons.append("campus + roll number match")
    elif roll_conflict:
        conflicts.append("different roll number")
    else:
        reasons.append("no roll number supplied")

    # -- name -------------------------------------------------------------
    similarity = name_similarity(entry.full_name, student.full_name)
    name_points = 0.0
    for threshold, points in _NAME_POINTS:
        if similarity >= threshold:
            name_points = points
            break
    score += name_points
    components["name"] = name_points
    if similarity >= 0.999:
        reasons.append("name matches exactly")
    elif similarity >= 0.92:
        reasons.append("name matches very closely")
    elif similarity >= 0.82:
        reasons.append("name matches closely (spelling may differ)")
    elif similarity >= 0.70:
        reasons.append("name is similar (spelling may differ)")
    elif similarity >= 0.62:
        reasons.append("name is loosely similar")
    else:
        conflicts.append("name differs")

    components["nickname"] = 0.0
    if entry.nickname and student.nickname:
        if normalize_text(entry.nickname) == normalize_text(student.nickname):
            score += W_NICKNAME
            components["nickname"] = W_NICKNAME
            reasons.append("nickname matches")

    # -- corroborating attributes -----------------------------------------
    components["course"] = 0.0
    if entry.course == student.course:
        score += W_COURSE
        components["course"] = W_COURSE
        reasons.append("course matches")
    elif "course" in hard_fields:
        conflicts.append(f"course says {entry.get_course_display()}")
    else:
        reasons.append("course differs (soft conflict)")

    components["year"] = 0.0
    if entry.year == student.year:
        score += W_YEAR
        components["year"] = W_YEAR
        reasons.append("year matches")
    elif "year" in hard_fields:
        conflicts.append(f"year says {entry.get_year_display()}")
    else:
        reasons.append("year differs (soft conflict)")

    components["section"] = 0.0
    entry_section = normalize_text(entry.section)
    student_section = normalize_text(student.section)
    if entry_section and student_section:
        if entry_section == student_section:
            score += W_SECTION
            components["section"] = W_SECTION
            reasons.append("section matches")
        elif "section" in hard_fields:
            conflicts.append(f"section says {entry.section}")
        else:
            reasons.append("section differs (soft conflict)")

    components["department"] = 0.0
    entry_dept = normalize_text(entry.department)
    student_dept = normalize_text(student.department)
    if entry_dept and student_dept:
        if entry_dept == student_dept:
            score += W_DEPARTMENT
            components["department"] = W_DEPARTMENT
            reasons.append("department matches")
    elif not entry_dept and not student_dept:
        components["department"] = W_DEPARTMENT * 0.4
        score += components["department"]
    else:
        components["department"] = W_DEPARTMENT * 0.25
        score += components["department"]

    confidence = round(min(score, 100.0), 2)

    # Auto-binding is intentionally narrow: exact roll, close name, no
    # contradictions, and (optionally) a student identity already verified by
    # staff. A missing or wrong roll can never auto-bind.
    attribute_conflict = bool(conflicts)
    auto_ok = (
        _auto_enabled()
        and roll_exact
        and similarity >= _auto_name_min()
        and not attribute_conflict
        and (student.is_verified or not _require_verified_for_auto())
    )

    return ScoredCandidate(
        student=student,
        score=confidence,
        name_similarity=similarity,
        reasons=reasons,
        conflicts=conflicts,
        roll_exact=roll_exact,
        roll_conflict=roll_conflict,
        auto_resolvable=auto_ok,
        components=components,
    )


def generate_candidates(entry: CrushEntry) -> list[ScoredCandidate]:
    """Rank plausible identity candidates for ``entry``.

    A candidate is kept when it is an exact roll match, an exact/close name
    match, or clears the configured advisory score. That lets a correct name
    with a mistyped roll reach a reviewer, while a random same-campus profile
    does not.
    """

    scored: list[ScoredCandidate] = []
    for student in candidate_pool(entry):
        verdict = score_candidate(entry, student)
        plausible = (
            verdict.roll_exact
            or verdict.name_similarity >= _name_candidate_min()
            or verdict.score >= _candidate_min_score()
        )
        if plausible:
            scored.append(verdict)

    scored.sort(
        key=lambda c: (c.roll_exact, c.score, c.name_similarity, -c.student.pk),
        reverse=True,
    )
    return scored[:_max_candidates()]


def _reviewed_candidate_ids(entry: CrushEntry) -> set[int]:
    return set(
        IdentityCandidate.objects.filter(
            crush_entry=entry,
            status__in=[
                IdentityCandidate.Status.REJECTED,
                IdentityCandidate.Status.DEFERRED,
            ],
        ).values_list("candidate_id", flat=True)
    )


def _sync_candidate_rows(
    entry: CrushEntry, scored: list[ScoredCandidate], *, actor=None
) -> dict[int, IdentityCandidate]:
    """Upsert candidate evidence without overwriting human decisions."""

    existing = {
        row.candidate_id: row
        for row in IdentityCandidate.objects.filter(crush_entry=entry)
    }
    keep_ids = {candidate.student.pk for candidate in scored}
    multiple = len(scored) > 1
    now = timezone.now()

    rows: dict[int, IdentityCandidate] = {}
    for candidate in scored:
        row = existing.get(candidate.student.pk)
        reviewed = row is not None and row.status in {
            IdentityCandidate.Status.CONFIRMED,
            IdentityCandidate.Status.REJECTED,
            IdentityCandidate.Status.DEFERRED,
        }
        default_status = (
            IdentityCandidate.Status.NEEDS_REVIEW
            if multiple or candidate.hard_conflict
            else IdentityCandidate.Status.CANDIDATE
        )
        defaults = {
            "confidence_score": candidate.score,
            "name_similarity": round(candidate.name_similarity, 3),
            "evidence": candidate.evidence,
            "status": row.status if reviewed else default_status,
            "scoring_version": IDENTITY_SCORING_VERSION,
            "scored_at": now,
        }
        if row is None:
            try:
                with transaction.atomic():
                    row = IdentityCandidate.objects.create(
                        crush_entry=entry,
                        candidate=candidate.student,
                        **defaults,
                    )
            except IntegrityError:
                # A concurrent resolver created the same unique row.
                row = IdentityCandidate.objects.get(
                    crush_entry=entry, candidate=candidate.student
                )
        else:
            row.confidence_score = candidate.score
            row.name_similarity = round(candidate.name_similarity, 3)
            row.evidence = candidate.evidence
            row.scoring_version = IDENTITY_SCORING_VERSION
            row.scored_at = now
            if not reviewed:
                row.status = default_status
            row.save(
                update_fields=[
                    "confidence_score",
                    "name_similarity",
                    "evidence",
                    "status",
                    "scoring_version",
                    "scored_at",
                    "updated_at",
                ]
            )
        rows[candidate.student.pk] = row

    # Rows that no longer describe a plausible candidate are retired, not
    # destroyed, so a reviewer can still see what was previously considered.
    stale = IdentityCandidate.objects.filter(crush_entry=entry).exclude(
        candidate_id__in=keep_ids
    )
    stale.filter(
        status__in=[
            IdentityCandidate.Status.CANDIDATE,
            IdentityCandidate.Status.NEEDS_REVIEW,
        ]
    ).update(status=IdentityCandidate.Status.SUPERSEDED, updated_at=timezone.now())
    return rows


def _audit(
    entry: CrushEntry,
    action: str,
    *,
    actor=None,
    candidate: StudentProfile | None = None,
    from_status: str = "",
    to_status: str = "",
    candidate_from_status: str = "",
    candidate_to_status: str = "",
    notes: str = "",
) -> None:
    IdentityResolutionAudit.objects.create(
        crush_entry=entry,
        candidate=candidate,
        actor=actor if getattr(actor, "pk", None) else None,
        action=action,
        from_status=from_status,
        to_status=to_status,
        candidate_from_status=candidate_from_status,
        candidate_to_status=candidate_to_status,
        notes=notes[:300],
    )


def bind_identity(
    entry: CrushEntry,
    student: StudentProfile,
    *,
    method: str,
    confidence: float,
    actor=None,
    notes: str = "",
    force: bool = False,
) -> CrushEntry:
    """Attach a verified internal student id to an entry.

    This is the only write path for ``resolved_student``. It re-checks the
    campus, self, block and account-validity rules under a row lock.
    """

    with transaction.atomic():
        locked = CrushEntry.objects.select_for_update().get(pk=entry.pk)
        if not locked.is_active:
            raise IdentityResolutionError("This crush entry is no longer active.")
        if locked.submitted_by_id == student.pk:
            raise IdentityResolutionError("A student cannot be their own crush.")
        if locked.college_id != locked.submitted_by.college_id:
            raise IdentityResolutionError("A crush cannot cross a campus boundary.")
        if locked.college_id != student.college_id:
            raise IdentityResolutionError("A crush cannot cross a campus boundary.")
        if not student.user.is_active:
            raise IdentityResolutionError("That account is not active.")
        if student.pk in _blocked_ids(locked.submitted_by):
            raise IdentityResolutionError("A block prevents this identity link.")
        now = timezone.now()

        row = IdentityCandidate.objects.filter(
            crush_entry=locked, candidate=student
        ).first()
        already_bound = (
            locked.resolved_student_id == student.pk
            and locked.identity_status == CrushEntry.ResolutionStatus.RESOLVED
        )
        if already_bound:
            # Idempotent retry: keep the binding and repair a missing candidate
            # row, but never append another audit event or overwrite a human
            # reviewer's notes with system text.
            if row is not None and row.status != IdentityCandidate.Status.CONFIRMED:
                row.status = IdentityCandidate.Status.CONFIRMED
                row.confidence_score = confidence
                row.scored_at = now
                row.scoring_version = IDENTITY_SCORING_VERSION
                row.save(
                    update_fields=[
                        "status",
                        "confidence_score",
                        "scored_at",
                        "scoring_version",
                        "updated_at",
                    ]
                )
            entry.refresh_from_db()
            return entry

        if locked.resolved_student_id and locked.resolved_student_id != student.pk:
            if not force:
                raise IdentityResolutionError(
                    "This entry is already resolved to a different student. "
                    "Reject or invalidate the existing link before rebinding."
                )

        previous_status = locked.identity_status
        previous_candidate_status = row.status if row is not None else ""
        locked.resolved_student = student
        locked.resolved_at = now
        locked.resolution_confidence = confidence
        locked.resolution_method = method
        locked.resolution_notes = notes[:300]
        locked.resolution_scoring_version = IDENTITY_SCORING_VERSION
        locked.resolution_scored_at = now
        locked.identity_status = CrushEntry.ResolutionStatus.RESOLVED
        locked.save(
            update_fields=[
                "resolved_student",
                "resolved_at",
                "resolution_confidence",
                "resolution_method",
                "resolution_notes",
                "resolution_scoring_version",
                "resolution_scored_at",
                "identity_status",
            ]
        )

        if row is not None:
            row.status = IdentityCandidate.Status.CONFIRMED
            row.confidence_score = confidence
            row.scoring_version = IDENTITY_SCORING_VERSION
            row.scored_at = now
            row.reviewed_by = actor if getattr(actor, "pk", None) else None
            row.reviewed_at = now if actor else row.reviewed_at
            if notes:
                row.review_notes = notes
            row.save(
                update_fields=[
                    "status",
                    "confidence_score",
                    "scoring_version",
                    "scored_at",
                    "reviewed_by",
                    "reviewed_at",
                    "review_notes",
                    "updated_at",
                ]
            )

        IdentityCandidate.objects.filter(
            crush_entry=locked,
            status__in=[
                IdentityCandidate.Status.CANDIDATE,
                IdentityCandidate.Status.NEEDS_REVIEW,
            ],
        ).exclude(candidate_id=student.pk).update(
            status=IdentityCandidate.Status.SUPERSEDED,
            updated_at=now,
        )

        action = (
            IdentityResolutionAudit.Action.CONFIRMED
            if actor
            else IdentityResolutionAudit.Action.AUTO_RESOLVED
        )
        _audit(
            locked,
            action,
            actor=actor,
            candidate=student,
            from_status=previous_status,
            to_status=locked.identity_status,
            candidate_from_status=previous_candidate_status,
            candidate_to_status=IdentityCandidate.Status.CONFIRMED,
            notes=notes or method,
        )

    entry.refresh_from_db()
    logger.info(
        "identity_resolved entry=%s student=%s method=%s", entry.pk, student.pk, method
    )
    return entry


def invalidate_resolution(
    entry: CrushEntry,
    reason: str,
    *,
    actor=None,
    to_status: str = CrushEntry.ResolutionStatus.PENDING,
) -> CrushEntry:
    """Remove a stale verified link, keeping the original typed evidence."""

    with transaction.atomic():
        locked = CrushEntry.objects.select_for_update().get(pk=entry.pk)
        previous = locked.identity_status
        if previous == CrushEntry.ResolutionStatus.RESOLVED or locked.resolved_student_id:
            _audit(
                locked,
                IdentityResolutionAudit.Action.INVALIDATED,
                actor=actor,
                candidate=locked.resolved_student,
                from_status=previous,
                to_status=to_status,
                notes=reason,
            )
        now = timezone.now()
        locked.identity_status = to_status
        locked.resolved_student = None
        locked.resolved_at = None
        locked.resolution_confidence = None
        locked.resolution_method = ""
        locked.resolution_notes = reason[:300]
        locked.resolution_scoring_version = IDENTITY_SCORING_VERSION
        locked.resolution_scored_at = now
        locked.save(
            update_fields=[
                "identity_status",
                "resolved_student",
                "resolved_at",
                "resolution_confidence",
                "resolution_method",
                "resolution_notes",
                "resolution_scoring_version",
                "resolution_scored_at",
            ]
        )
        # Pending match proposals must not survive an invalid identity. Retire
        # them as STALE so the reason survives for audit. An already-approved
        # match is a human decision and is left for review.
        PotentialMatch.objects.filter(
            crush_entry=locked, status=PotentialMatch.Status.PENDING
        ).update(
            status=PotentialMatch.Status.STALE,
            invalidated_reason=reason[:300],
            scored_at=now,
        )
        # If we invalidated a resolved link, any confirmed identity candidate
        # tied to that resolved student should no longer remain confirmed
        if locked.resolved_student_id is None and previous == CrushEntry.ResolutionStatus.RESOLVED:
            # Supersede confirmed candidates that pointed to the old resolved student
            from .models import IdentityCandidate

            IdentityCandidate.objects.filter(
                crush_entry=locked, status=IdentityCandidate.Status.CONFIRMED
            ).update(status=IdentityCandidate.Status.SUPERSEDED, updated_at=now)

    entry.refresh_from_db()
    return entry


def _set_status(entry: CrushEntry, status: str, reason: str = "") -> CrushEntry:
    if entry.identity_status == status and (not reason or entry.resolution_notes == reason):
        entry.resolution_scoring_version = IDENTITY_SCORING_VERSION
        entry.resolution_scored_at = timezone.now()
        entry.save(
            update_fields=["resolution_scoring_version", "resolution_scored_at"]
        )
        return entry
    previous = entry.identity_status
    entry.identity_status = status
    if reason:
        entry.resolution_notes = reason[:300]
    entry.resolution_scoring_version = IDENTITY_SCORING_VERSION
    entry.resolution_scored_at = timezone.now()
    entry.save(
        update_fields=[
            "identity_status",
            "resolution_notes",
            "resolution_scoring_version",
            "resolution_scored_at",
        ]
    )
    logger.debug(
        "identity_status entry=%s from=%s to=%s", entry.pk, previous, status
    )
    return entry


def _blocking_identity_conflicts(scored: ScoredCandidate) -> list[str]:
    """Conflicts that must break an existing link.

    A name correction is explicitly *not* one of them: the roll number is the
    identity key, and the student may fix a misspelled name without losing the
    verified relationship. Roll and hard-field conflicts still block.
    """

    conflicts = [str(conflict) for conflict in (scored.conflicts or [])]
    if scored.roll_conflict and not any(
        "roll" in conflict.lower() for conflict in conflicts
    ):
        conflicts.append("different roll number")
    return [
        conflict
        for conflict in conflicts
        if conflict.strip().lower() != "name differs"
    ]


def resolve_entry(
    entry: CrushEntry,
    *,
    force: bool = False,
    actor=None,
) -> CrushEntry:
    """Recompute the identity state for one entry.

    Idempotent: safe to call on submit, edit, registration, admin correction and
    maintenance sweeps. It never creates a ``MutualMatch`` or notification.
    """

    if not entry.pk:
        return entry
    entry.refresh_from_db()
    if not entry.is_active:
        return entry
    if entry.identity_status == CrushEntry.ResolutionStatus.UNRESOLVABLE and not force:
        return entry
    if entry.college_id != entry.submitted_by.college_id:
        return invalidate_resolution(
            entry,
            "A crush must stay within the submitting student's campus.",
            actor=actor,
        )

    scored = generate_candidates(entry)
    _sync_candidate_rows(entry, scored, actor=actor)
    reviewed = _reviewed_candidate_ids(entry)

    open_candidates = [c for c in scored if c.student.pk not in reviewed]
    auto_candidates = [c for c in open_candidates if c.auto_resolvable]
    current = entry.resolved_student
    current_scored = next(
        (c for c in scored if current and c.student.pk == current.pk), None
    )

    # -- existing verified link: keep, refresh, or invalidate ---------------
    if current is not None:
        try:
            if entry.submitted_by_id == current.pk:
                invalidate_resolution(entry, "Self-match is not allowed.", actor=actor)
                current = None
                current_scored = None
            elif getattr(entry, "college_id") and getattr(current, "college_id") and entry.college_id != current.college_id:
                invalidate_resolution(entry, "Cross-campus identity is not allowed.", actor=actor)
                current = None
                current_scored = None
            elif current.user_id and not getattr(current.user, "is_active", True):
                invalidate_resolution(entry, "Account is no longer active.", actor=actor)
                current = None
                current_scored = None
            elif current.pk in _blocked_ids(entry.submitted_by):
                invalidate_resolution(entry, "A block prevents this identity link.", actor=actor)
                current = None
                current_scored = None
        except Exception:
            pass
    if current is not None:
        auto = auto_candidates[0] if len(auto_candidates) == 1 else None
        is_manual = getattr(entry, "resolution_method", "") in ("admin_confirmed",) or bool(
            IdentityCandidate.objects.filter(
                crush_entry=entry, candidate=current, status=IdentityCandidate.Status.CONFIRMED
            ).exclude(reviewed_by=None).exists()
        ) or getattr(entry, "resolution_method", "").startswith("admin")
        # Better check: look up confirmed candidate for this entry+student
        if auto is not None and auto.student.pk != current.pk:
            # Don't blindly invalidate a manual confirmation
            if is_manual or getattr(entry, "resolution_method", "") == "admin_confirmed":
                entry.resolution_confidence = current_scored.score if current_scored else entry.resolution_confidence
                entry.resolution_scoring_version = IDENTITY_SCORING_VERSION
                entry.resolution_scored_at = timezone.now()
                entry.save(
                    update_fields=[
                        "resolution_confidence",
                        "resolution_scoring_version",
                        "resolution_scored_at",
                    ]
                )
            else:
                invalidate_resolution(
                    entry,
                    "Entry evidence now points to a different candidate.",
                    actor=actor,
                )
                current = None
                current_scored = None
        elif current_scored is None:
            # If manually confirmed and we just can't find current in re-scoring due to
            # bad entry data, don't invalidate
            if is_manual or getattr(entry, "resolution_method", "") == "admin_confirmed":
                entry.resolution_scoring_version = IDENTITY_SCORING_VERSION
                entry.resolution_scored_at = timezone.now()
                entry.save(
                    update_fields=[
                        "resolution_scoring_version",
                        "resolution_scored_at",
                    ]
                )
            else:
                invalidate_resolution(
                    entry,
                    "The verified student no longer matches the submitted details.",
                    actor=actor,
                    to_status=CrushEntry.ResolutionStatus.NEEDS_REVIEW,
                )
                current = None
        else:
            blocking_conflicts = _blocking_identity_conflicts(current_scored)
            if is_manual or getattr(entry, "resolution_method", "") == "admin_confirmed":
                entry.resolution_confidence = current_scored.score
                entry.resolution_scoring_version = IDENTITY_SCORING_VERSION
                entry.resolution_scored_at = timezone.now()
                entry.save(
                    update_fields=[
                        "resolution_confidence",
                        "resolution_scoring_version",
                        "resolution_scored_at",
                    ]
                )
            elif blocking_conflicts:
                if any("roll" in conflict.lower() for conflict in blocking_conflicts):
                    msg = "Roll number conflict needs human review."
                elif any(
                    field in conflict.lower()
                    for field in ("course", "year", "section")
                    for conflict in blocking_conflicts
                ):
                    msg = "A course, year or section conflict needs human review."
                else:
                    msg = (
                        "; ".join(blocking_conflicts)[:200]
                        or "Identity conflict needs human review."
                    )
                invalidate_resolution(
                    entry,
                    msg,
                    actor=actor,
                    to_status=CrushEntry.ResolutionStatus.NEEDS_REVIEW,
                )
                current = None
            else:
                # A name correction on an already-verified student is not a
                # reason to destroy the link. Keep the verified roll identity
                # and update the advisory confidence score.
                entry.resolution_confidence = current_scored.score
                entry.resolution_scoring_version = IDENTITY_SCORING_VERSION
                entry.resolution_scored_at = timezone.now()
                entry.save(
                    update_fields=[
                        "resolution_confidence",
                        "resolution_scoring_version",
                        "resolution_scored_at",
                    ]
                )

    # -- no verified link: auto-bind only the single safe candidate ---------
    if current is None and len(auto_candidates) == 1:
        candidate = auto_candidates[0]
        try:
            bind_identity(
                entry,
                candidate.student,
                method="auto_exact_roll",
                confidence=candidate.score,
                notes="Campus, roll number and name agree.",
            )
        except IdentityResolutionError:
            # A concurrent edit/block changed the evidence between scoring and
            # binding. Leave the entry for a human instead of failing the request.
            return _set_status(
                entry,
                CrushEntry.ResolutionStatus.NEEDS_REVIEW,
                "Identity evidence changed during resolution; review is required.",
            )
        entry.refresh_from_db()
        current = entry.resolved_student
        current_scored = candidate

    if current is not None:
        return entry

    # -- stay unresolved, with a safe review path --------------------------
    if not open_candidates:
        if scored:
            # Every candidate was already rejected/deferred by a reviewer.
            return _set_status(
                entry,
                CrushEntry.ResolutionStatus.NEEDS_REVIEW,
                "All possible candidates have been reviewed; no safe automatic link remains.",
            )
        return _set_status(
            entry,
            CrushEntry.ResolutionStatus.PENDING,
            "No registered student matches yet; this will be checked again when someone joins.",
        )

    if len(open_candidates) == 1 and not open_candidates[0].hard_conflict:
        return _set_status(
            entry,
            CrushEntry.ResolutionStatus.CANDIDATE_FOUND,
            "One possible identity found; review is required before linking.",
        )

    return _set_status(
        entry,
        CrushEntry.ResolutionStatus.NEEDS_REVIEW,
        "Multiple or conflicting identity candidates need human review.",
    )


def _possible_entries_for(student: StudentProfile) -> list[CrushEntry]:
    """Bounded query for entries a newly registered/edited student may resolve."""

    base = (
        CrushEntry.objects.active()
        .filter(college_id=student.college_id)
        .exclude(submitted_by=student)
        .select_related("submitted_by", "college", "resolved_student")
    )
    scope = Q(resolved_student=student) | Q(
        identity_status__in=[
            CrushEntry.ResolutionStatus.PENDING,
            CrushEntry.ResolutionStatus.CANDIDATE_FOUND,
            CrushEntry.ResolutionStatus.NEEDS_REVIEW,
        ]
    )
    possible = Q(resolved_student=student) | Q(
        potential_matches__registered_student=student,
        potential_matches__status=PotentialMatch.Status.PENDING,
    )
    if student.normalized_roll_number:
        possible |= Q(normalized_roll_number=student.normalized_roll_number)
    if student.normalized_name:
        possible |= Q(normalized_name=student.normalized_name)
        for token in set(student.normalized_name.split()):
            if token:
                possible |= Q(normalized_name__startswith=token[0]) | Q(
                    normalized_name__contains=f" {token[0]}"
                )
    limit = int(_setting("IDENTITY_REGISTRATION_SCAN_LIMIT", 500))
    return list(base.filter(scope).filter(possible).order_by("pk")[:limit])


def refresh_for_student(student: StudentProfile) -> list[PotentialMatch]:
    """Resolve entries affected by a registration or profile edit.

    Both directions are covered:
      * entries that describe this student (including a changed roll/name);
      * this student's own entries, through the normal match path.
    """

    from . import matching

    entries = {entry.pk: entry for entry in _possible_entries_for(student)}
    for entry in (
        CrushEntry.objects.active()
        .filter(submitted_by=student)
        .select_related("submitted_by", "college", "resolved_student")
    ):
        entries[entry.pk] = entry

    created: list[PotentialMatch] = []
    for entry in entries.values():
        resolve_entry(entry)
        created.extend(matching.propose_for_entry(entry, resolve=False))
    return created


def confirm_candidate(
    candidate: IdentityCandidate, actor, *, notes: str = ""
) -> CrushEntry:
    """Reviewer confirms a candidate, binding it explicitly.

    Idempotent for an already-confirmed row. Rejected, deferred and superseded
    rows must be explicitly reopened first, so a reviewer can never revive an
    old decision by accident.
    """

    with transaction.atomic():
        candidate = (
            IdentityCandidate.objects.select_for_update()
            .select_related("crush_entry", "candidate")
            .get(pk=candidate.pk)
        )
        entry = candidate.crush_entry

        if candidate.status == IdentityCandidate.Status.CONFIRMED and (
            entry.resolved_student_id == candidate.candidate_id
        ):
            if notes and notes != candidate.review_notes:
                candidate.review_notes = notes
                candidate.save(update_fields=["review_notes", "updated_at"])
            entry.refresh_from_db()
            return entry

        if candidate.status in {
            IdentityCandidate.Status.REJECTED,
            IdentityCandidate.Status.DEFERRED,
            IdentityCandidate.Status.SUPERSEDED,
        }:
            raise IdentityResolutionError(
                "Reopen this candidate before confirming it."
            )

        bind_identity(
            entry,
            candidate.candidate,
            method="admin_confirmed",
            confidence=float(candidate.confidence_score or 0),
            actor=actor,
            notes=notes,
        )
        candidate.refresh_from_db()
        candidate.status = IdentityCandidate.Status.CONFIRMED
        candidate.reviewed_by = actor
        candidate.reviewed_at = timezone.now()
        if notes:
            candidate.review_notes = notes
        candidate.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "review_notes",
                "updated_at",
            ]
        )
    from . import matching

    entry.refresh_from_db()
    matching.propose_for_entry(entry, resolve=False)
    return entry


def reject_candidate(
    candidate: IdentityCandidate, actor, *, notes: str = ""
) -> CrushEntry:
    """Reviewer rejects a candidate. The row stays rejected and cannot auto-bind."""

    with transaction.atomic():
        candidate = (
            IdentityCandidate.objects.select_for_update()
            .select_related("crush_entry", "candidate")
            .get(pk=candidate.pk)
        )
        entry = candidate.crush_entry
        if candidate.status == IdentityCandidate.Status.REJECTED:
            if notes and notes != candidate.review_notes:
                candidate.review_notes = notes
                candidate.save(update_fields=["review_notes", "updated_at"])
            entry.refresh_from_db()
            return entry
        previous = entry.identity_status
        previous_candidate_status = candidate.status
        candidate.status = IdentityCandidate.Status.REJECTED
        candidate.reviewed_by = actor
        candidate.reviewed_at = timezone.now()
        candidate.review_notes = notes
        candidate.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "review_notes",
                "updated_at",
            ]
        )
        if entry.resolved_student_id == candidate.candidate_id:
            invalidate_resolution(
                entry,
                "Reviewer rejected the identity link.",
                actor=actor,
                to_status=CrushEntry.ResolutionStatus.NEEDS_REVIEW,
            )
        _audit(
            entry,
            IdentityResolutionAudit.Action.REJECTED,
            actor=actor,
            candidate=candidate.candidate,
            from_status=previous,
            to_status=entry.identity_status,
            candidate_from_status=previous_candidate_status,
            candidate_to_status=IdentityCandidate.Status.REJECTED,
            notes=notes,
        )
    entry.refresh_from_db()
    # Recompute alternatives; the rejected row is sticky and excluded from auto.
    resolve_entry(entry)
    from . import matching

    matching.propose_for_entry(entry, resolve=False)
    return entry


def defer_candidate(
    candidate: IdentityCandidate, actor, *, notes: str = ""
) -> CrushEntry:
    """Reviewer parks a candidate. It is preserved but never auto-bound."""

    with transaction.atomic():
        candidate = (
            IdentityCandidate.objects.select_for_update()
            .select_related("crush_entry", "candidate")
            .get(pk=candidate.pk)
        )
        entry = candidate.crush_entry
        if candidate.status == IdentityCandidate.Status.DEFERRED:
            if notes and notes != candidate.review_notes:
                candidate.review_notes = notes
                candidate.save(update_fields=["review_notes", "updated_at"])
            entry.refresh_from_db()
            return entry
        previous = entry.identity_status
        previous_candidate_status = candidate.status
        candidate.status = IdentityCandidate.Status.DEFERRED
        candidate.reviewed_by = actor
        candidate.reviewed_at = timezone.now()
        candidate.review_notes = notes
        candidate.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "review_notes",
                "updated_at",
            ]
        )
        if entry.resolved_student_id == candidate.candidate_id:
            invalidate_resolution(
                entry,
                "Reviewer deferred the identity link.",
                actor=actor,
                to_status=CrushEntry.ResolutionStatus.NEEDS_REVIEW,
            )
        _audit(
            entry,
            IdentityResolutionAudit.Action.DEFERRED,
            actor=actor,
            candidate=candidate.candidate,
            from_status=previous,
            to_status=entry.identity_status,
            candidate_from_status=previous_candidate_status,
            candidate_to_status=IdentityCandidate.Status.DEFERRED,
            notes=notes,
        )
    entry.refresh_from_db()
    return entry


def reopen_candidate(
    candidate: IdentityCandidate, actor, *, notes: str = ""
) -> CrushEntry:
    """Undo a sticky reject/defer so the candidate can be reviewed again."""

    with transaction.atomic():
        candidate = (
            IdentityCandidate.objects.select_for_update()
            .select_related("crush_entry", "candidate")
            .get(pk=candidate.pk)
        )
        if candidate.status not in {
            IdentityCandidate.Status.REJECTED,
            IdentityCandidate.Status.DEFERRED,
            IdentityCandidate.Status.SUPERSEDED,
        }:
            raise IdentityResolutionError("Only a closed candidate can be reopened.")
        entry = candidate.crush_entry
        previous = entry.identity_status
        previous_candidate_status = candidate.status
        candidate.status = IdentityCandidate.Status.NEEDS_REVIEW
        candidate.reviewed_by = actor
        candidate.reviewed_at = timezone.now()
        candidate.review_notes = notes
        candidate.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "review_notes",
                "updated_at",
            ]
        )
        _audit(
            entry,
            IdentityResolutionAudit.Action.REOPENED,
            actor=actor,
            candidate=candidate.candidate,
            from_status=previous,
            to_status=previous,
            candidate_from_status=previous_candidate_status,
            candidate_to_status=IdentityCandidate.Status.NEEDS_REVIEW,
            notes=notes or "Identity candidate reopened.",
        )
    entry.refresh_from_db()
    return entry


def mark_unresolvable(entry: CrushEntry, actor, *, notes: str = "") -> CrushEntry:
    """Explicitly close identity resolution for an entry; no link is kept."""

    with transaction.atomic():
        entry = CrushEntry.objects.select_for_update().get(pk=entry.pk)
        previous = entry.identity_status
        now = timezone.now()
        entry.identity_status = CrushEntry.ResolutionStatus.UNRESOLVABLE
        entry.resolved_student = None
        entry.resolved_at = None
        entry.resolution_confidence = None
        entry.resolution_method = ""
        entry.resolution_notes = notes[:300]
        entry.resolution_scoring_version = IDENTITY_SCORING_VERSION
        entry.resolution_scored_at = now
        entry.save(
            update_fields=[
                "identity_status",
                "resolved_student",
                "resolved_at",
                "resolution_confidence",
                "resolution_method",
                "resolution_notes",
                "resolution_scoring_version",
                "resolution_scored_at",
            ]
        )
        PotentialMatch.objects.filter(
            crush_entry=entry, status=PotentialMatch.Status.PENDING
        ).update(
            status=PotentialMatch.Status.STALE,
            invalidated_reason="Entry was marked unresolvable.",
            scored_at=now,
        )
        _audit(
            entry,
            IdentityResolutionAudit.Action.UNRESOLVABLE,
            actor=actor,
            from_status=previous,
            to_status=entry.identity_status,
            notes=notes,
        )
    entry.refresh_from_db()
    return entry


def reopen_entry(entry: CrushEntry, actor, *, notes: str = "") -> CrushEntry:
    """Put an unresolvable entry back into safe automatic processing."""

    with transaction.atomic():
        entry = CrushEntry.objects.select_for_update().get(pk=entry.pk)
        previous = entry.identity_status
        entry.identity_status = CrushEntry.ResolutionStatus.PENDING
        entry.resolution_notes = notes[:300]
        entry.save(update_fields=["identity_status", "resolution_notes"])
        _audit(
            entry,
            IdentityResolutionAudit.Action.REOPENED,
            actor=actor,
            from_status=previous,
            to_status=entry.identity_status,
            notes=notes,
        )
    return resolve_entry(entry, force=True)


def retire_entry(entry: CrushEntry, *, actor=None) -> None:
    """Clean up match state when a student removes a crush slot."""

    with transaction.atomic():
        entry = CrushEntry.objects.select_for_update().get(pk=entry.pk)
        now = timezone.now()
        PotentialMatch.objects.filter(
            crush_entry=entry, status=PotentialMatch.Status.PENDING
        ).update(
            status=PotentialMatch.Status.STALE,
            invalidated_reason="Crush entry was removed.",
            scored_at=now,
        )
        IdentityCandidate.objects.filter(
            crush_entry=entry,
            status__in=[
                IdentityCandidate.Status.CANDIDATE,
                IdentityCandidate.Status.NEEDS_REVIEW,
            ],
        ).update(status=IdentityCandidate.Status.SUPERSEDED, updated_at=timezone.now())
        if entry.identity_status == CrushEntry.ResolutionStatus.RESOLVED:
            _audit(
                entry,
                IdentityResolutionAudit.Action.INVALIDATED,
                actor=actor,
                candidate=entry.resolved_student,
                from_status=entry.identity_status,
                to_status=CrushEntry.ResolutionStatus.PENDING,
                notes="Crush entry was removed.",
            )
        entry.resolved_student = None
        entry.resolved_at = None
        entry.resolution_confidence = None
        entry.resolution_method = ""
        entry.resolution_scoring_version = IDENTITY_SCORING_VERSION
        entry.resolution_scored_at = now
        entry.identity_status = CrushEntry.ResolutionStatus.PENDING
        entry.save(
            update_fields=[
                "resolved_student",
                "resolved_at",
                "resolution_confidence",
                "resolution_method",
                "resolution_scoring_version",
                "resolution_scored_at",
                "identity_status",
            ]
        )
