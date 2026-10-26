"""Identity matching for hand-typed crush entries (requirements 7/8/18/19/20).

The product deliberately removed student search, so this module is the *only*
thing that ever connects a typed ``CrushEntry`` to a real ``StudentProfile``.

Two rules govern everything here:

1. **College + normalized roll number is the identity gate.** Nothing is ever
   proposed without both matching exactly, so "Riya Sharma roll 21" and "Riya
   Sharma roll 47" stay two different people (requirements 7/19).
2. **A proposal is never a result.** Every hit lands in ``PotentialMatch`` with
   status ``pending`` and no user notification. A human has to approve it
   (requirements 10/18/26).

Name similarity only moves the advisory confidence score, because names have
too many spelling variants to carry identity on their own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from django.db import IntegrityError, transaction

from .models import (
    Block,
    CrushEntry,
    PotentialMatch,
    StudentProfile,
    name_tokens,
    normalize_name,
    normalize_roll_number,
    normalize_text,
)

# --- confidence weights (sum to 100) ---------------------------------------
W_NAME = 40.0
W_COURSE = 20.0
W_YEAR = 15.0
W_SECTION = 10.0
W_DEPARTMENT = 8.0
W_NICKNAME = 7.0

# Below this, a proposal is not even worth an admin's time. Anything that gets
# through the identity gate and the disqualifiers lands at >= 44, so this only
# filters genuinely degenerate rows.
MIN_CONFIDENCE = 40.0

_NAME_SIMILAR_ENOUGH = 0.62


@dataclass
class MatchVerdict:
    """Outcome of comparing one entry against one registered student."""

    eligible: bool
    confidence: float
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def rejected(self) -> str | None:
        return "; ".join(self.blockers) if self.blockers else None


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def name_similarity(left: str, right: str) -> float:
    """0..1 similarity between two names, tolerant of spelling drift.

    Handles the variants requirements 7 calls out -- Niki/Nikki/Nikita/Nikhita,
    Riya/Ria/Rhea -- by combining whole-string similarity with per-token
    similarity, so a single misspelled token does not sink the whole score.
    """
    a, b = normalize_name(left), normalize_name(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    whole = _ratio(a, b)
    ta, tb = a.split(), b.split()
    best_token = 0.0
    for x in ta:
        for y in tb:
            if x == y:
                best_token = 1.0
                break
            best_token = max(best_token, _ratio(x, y))
        if best_token == 1.0:
            break

    overlap = len(set(ta) & set(tb))
    union = len(set(ta) | set(tb)) or 1
    jaccard = overlap / union

    return max(whole, 0.6 * best_token + 0.4 * jaccard)


def _name_points(similarity: float) -> float:
    if similarity >= 0.999:
        return W_NAME
    if similarity >= 0.88:
        return W_NAME * 0.92
    if similarity >= 0.78:
        return W_NAME * 0.78
    if similarity >= 0.62:
        return W_NAME * 0.55
    return 0.0


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def compare(entry: CrushEntry, student: StudentProfile) -> MatchVerdict:
    """Score ``entry`` against ``student``. Never raises, never mutates."""
    reasons: list[str] = []
    blockers: list[str] = []

    # -- identity gate -----------------------------------------------------
    if entry.college_id != student.college_id:
        return MatchVerdict(False, 0.0, blockers=["different campus"])
    if entry.submitted_by_id == student.pk:
        return MatchVerdict(False, 0.0, blockers=["same student"])

    if entry.resolved_student_id:
        # Identity resolution has already done the hard work. Keep the link
        # authoritative, but still refuse a hard course/year/section
        # contradiction: that is evidence two different people were blended.
        if entry.resolved_student_id != student.pk:
            if (
                entry.normalized_roll_number
                and entry.normalized_roll_number != student.normalized_roll_number
            ):
                return MatchVerdict(False, 0.0, blockers=["different roll number"])
            return MatchVerdict(
                False, 0.0, blockers=["resolved to a different student"]
            )
        reasons.append("identity confirmed by resolution")
    else:
        # Legacy/unresolved path: the original exact college + roll gate is
        # retained so direct comparisons stay conservative.
        if not entry.normalized_roll_number or (
            entry.normalized_roll_number != student.normalized_roll_number
        ):
            return MatchVerdict(False, 0.0, blockers=["different roll number"])
        reasons.append("campus + roll number match")

    score = 0.0

    # -- name (soft signal only) ------------------------------------------
    similarity = name_similarity(entry.full_name, student.full_name)
    score += _name_points(similarity)
    if similarity >= 0.999:
        reasons.append("name matches exactly")
    elif similarity >= 0.88:
        reasons.append("name matches closely")
    elif similarity >= 0.62:
        reasons.append("name similar (spelling may differ)")
    else:
        reasons.append("name differs but roll number is exact")

    if entry.nickname and student.nickname:
        if normalize_text(entry.nickname) == normalize_text(student.nickname):
            score += W_NICKNAME
            reasons.append("nickname matches")

    # -- course ------------------------------------------------------------
    if entry.course == student.course:
        score += W_COURSE
        reasons.append("course matches")
    else:
        blockers.append(f"course says {entry.get_course_display()}")

    # -- year --------------------------------------------------------------
    if entry.year == student.year:
        score += W_YEAR
        reasons.append("year matches")
    else:
        blockers.append(f"year says {entry.get_year_display()}")

    # -- section (blank on either side is not a contradiction) -------------
    entry_section = normalize_text(entry.section)
    student_section = normalize_text(student.section)
    if entry_section and student_section:
        if entry_section == student_section:
            score += W_SECTION
            reasons.append("section matches")
        else:
            blockers.append(f"section says {entry.section}")

    # -- department -------------------------------------------------------
    entry_dept = normalize_text(entry.department)
    student_dept = normalize_text(student.department)
    if entry_dept and student_dept:
        if entry_dept == student_dept:
            score += W_DEPARTMENT
            reasons.append("department matches")
    elif not entry_dept and not student_dept:
        score += W_DEPARTMENT * 0.4
    elif entry_dept or student_dept:
        score += W_DEPARTMENT * 0.25

    # A hard contradiction on course, year or section disqualifies the pair
    # outright: that is two people who happen to share a roll number
    # (requirement 18).
    eligible = not blockers
    return MatchVerdict(eligible, round(score, 2), reasons, blockers)


# ---------------------------------------------------------------------------
# Proposal creation
# ---------------------------------------------------------------------------


def _reason_text(verdict: MatchVerdict) -> str:
    return ", ".join(verdict.reasons or verdict.blockers)[:300]


def _refresh_resolved_proposal(match: PotentialMatch) -> None:
    verdict = compare(match.crush_entry, match.registered_student)
    match.confidence_score = verdict.confidence
    match.match_reasons = _reason_text(verdict)
    match.save(update_fields=["confidence_score", "match_reasons"])


def _sync_pending_proposal(
    entry: CrushEntry, student: StudentProfile, verdict: MatchVerdict
) -> PotentialMatch | None:
    """Create or refresh one proposal, or drop it if it no longer fits.

    Pending rows that stop qualifying are deleted. Reviewed rows keep their
    status -- an approval or rejection is never silently undone -- but their
    advisory score still reflects the latest edited details.
    """
    # A reviewer-confirmed identity is sufficient even when the typed details
    # are sparse; the score is advisory. Unresolved entries still need the
    # normal confidence floor before a proposal is worth an admin's time.
    qualified = verdict.eligible and (
        bool(entry.resolved_student_id) or verdict.confidence >= MIN_CONFIDENCE
    )
    match = PotentialMatch.objects.filter(
        crush_entry=entry, registered_student=student
    ).first()

    if match is None:
        if not qualified:
            return None
        try:
            with transaction.atomic():
                return PotentialMatch.objects.create(
                    crush_entry=entry,
                    registered_student=student,
                    confidence_score=verdict.confidence,
                    match_reasons=_reason_text(verdict),
                    status=PotentialMatch.Status.PENDING,
                )
        except IntegrityError:
            # A concurrent matcher created the same unique proposal.
            match = PotentialMatch.objects.get(
                crush_entry=entry, registered_student=student
            )

    if match.status == PotentialMatch.Status.PENDING and not qualified:
        match.delete()
        return None

    match.confidence_score = verdict.confidence
    match.match_reasons = _reason_text(verdict)
    match.save(update_fields=["confidence_score", "match_reasons"])
    return None


def _proposal_candidates(entry: CrushEntry) -> list[StudentProfile]:
    """The only students a proposal may point at for this entry.

    A resolved entry points at exactly its verified identity. The unresolved
    fallback preserves the old exact-roll proposal path for legacy rows; it
    still cannot become a confirmed match until approval re-checks resolution.
    """

    author = entry.submitted_by
    base = StudentProfile.objects.filter(
        college_id=entry.college_id, user__is_active=True
    ).exclude(pk=author.pk).exclude(pk__in=_blocked_ids(author))

    if entry.resolved_student_id:
        return list(base.filter(pk=entry.resolved_student_id))

    if not entry.normalized_roll_number:
        return []
    return list(base.filter(normalized_roll_number=entry.normalized_roll_number))


@transaction.atomic
def propose_for_entry(
    entry: CrushEntry, *, resolve: bool = True
) -> list[PotentialMatch]:
    """Find registered students matching ``entry`` and queue them for review.

    Resolves identity first (unless the caller just did so), refreshes existing
    pending rows in place, and removes rows that no longer fit because the entry
    was edited or blocked. Returns only rows newly created.
    """

    if not entry.is_active:
        return []

    if resolve:
        from .identity_resolution import resolve_entry

        resolve_entry(entry)
        entry.refresh_from_db()

    if not entry.resolved_student_id and not entry.normalized_roll_number:
        return []

    candidates = _proposal_candidates(entry)
    candidate_ids = [student.pk for student in candidates]

    created: list[PotentialMatch] = []
    for student in candidates:
        new_match = _sync_pending_proposal(entry, student, compare(entry, student))
        if new_match is not None:
            created.append(new_match)

    # An edited entry may now point somewhere else entirely.
    PotentialMatch.objects.filter(
        crush_entry=entry, status=PotentialMatch.Status.PENDING
    ).exclude(registered_student_id__in=candidate_ids).delete()
    stale_reviewed = PotentialMatch.objects.filter(crush_entry=entry).exclude(
        registered_student_id__in=candidate_ids
    )
    for match in stale_reviewed:
        _refresh_resolved_proposal(match)
    return created


def refresh_incoming_matches(student: StudentProfile) -> list[PotentialMatch]:
    """Resolve/re-score every entry affected by a registration or profile edit.

    Delegates to the identity service so name-only and missing-roll entries get
    the same safe treatment as the submit-time path.
    """
    from .identity_resolution import refresh_for_student

    return refresh_for_student(student)


def match_entries_for(author: StudentProfile) -> list[PotentialMatch]:
    """Match every active entry ``author`` has submitted."""
    created: list[PotentialMatch] = []
    for entry in CrushEntry.objects.active().filter(submitted_by=author):
        created.extend(propose_for_entry(entry))
    return created


def match_new_student(student: StudentProfile) -> list[PotentialMatch]:
    """Run when someone registers or edits their campus identity.

    Two directions matter (requirement 8):
    entries that describe *this* student, and this student's own entries
    that describe people who were already registered.
    """
    created = refresh_incoming_matches(student)

    # Direction 2: this student's own entries vs already-registered students.
    created.extend(match_entries_for(student))
    return created


def _blocked_ids(student: StudentProfile) -> list[int]:
    outgoing = Block.objects.filter(blocker=student).values_list("blocked_id", flat=True)
    incoming = Block.objects.filter(blocked=student).values_list("blocker_id", flat=True)
    return list({*outgoing, *incoming})


# ---------------------------------------------------------------------------
# Review helpers
# ---------------------------------------------------------------------------


def pending_pairs() -> list[dict]:
    """Reciprocal proposals grouped into one row per pair, best first.

    Only pairs where *both* students submitted each other are returned: a
    one-sided entry can never become a mutual crush, so it is not something an
    admin can meaningfully approve (requirement 18).
    """
    rows: dict[tuple[int, int], dict] = {}
    for match in PotentialMatch.objects.for_review().pending().order_by("pk"):
        partner = match.reciprocal
        if partner is None:
            continue
        key = match.pair_key
        if key in rows:
            continue
        scores = [m.confidence_score for m in (match, partner) if m.confidence_score]
        rows[key] = {
            "key": key,
            "forward": match,
            "backward": partner,
            "confidence": max(scores) if scores else None,
        }
    ordered = sorted(
        rows.values(),
        key=lambda r: (r["confidence"] is None, -(r["confidence"] or 0)),
    )
    return ordered


def unpaired_pending() -> list[PotentialMatch]:
    """Pending proposals with no reciprocal half, for completeness."""
    return [
        m
        for m in PotentialMatch.objects.for_review().pending().order_by("pk")
        if m.reciprocal is None
    ]