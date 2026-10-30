"""Tests for the rules the crush-flow spec is strictest about.

Invariants under test:
  * campus + normalized roll number is the identity gate (requirements 7/19)
  * a proposal is never a result: sealing never notifies anyone (17)
  * only an admin approval can create a MutualMatch or notify (10/14/15/24)
  * priority never reaches a student's browser (13/16)
  * one list slot per priority, max three, no self, no duplicate (2/3/18)
"""

import datetime as dt
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from .forms import CrushEntryForm, StudentIdentityForm
from .identity_resolution import (
    confirm_candidate,
    mark_unresolvable,
    reject_candidate,
    reopen_candidate,
    resolve_entry,
    score_candidate,
)
from .matching import MIN_CONFIDENCE, compare, pending_pairs
from .models import (
    MAX_CRUSHES,
    Block,
    College,
    CrushEntry,
    IdentityCandidate,
    IdentityResolutionAudit,
    MutualMatch,
    Notification,
    PotentialMatch,
    StudentProfile,
    normalize_name,
    normalize_roll_number,
)
from .services import (
    ApprovalError,
    SelectionError,
    approve_potential_match,
    campus_status,
    reject_potential_match,
    seal_secret,
)

User = get_user_model()


def make_student(college, roll, name="Student", **kwargs):
    email = f"{roll.lower()}@{college.pk}{college.name[:3].lower()}.example.edu"
    user = User.objects.create_user(username=email, email=email, password="x")
    defaults = {
        "college": college,
        "full_name": name,
        "roll_number": roll,
        "course": "BCA",
        "year": 2,
        "section": "A",
        "department": "",
        "date_of_birth": dt.date.today().replace(year=dt.date.today().year - 20),
    }
    defaults.update(kwargs)
    return StudentProfile.objects.create(user=user, **defaults)


def make_entry(author, target, priority=1, **overrides):
    """A hand-typed entry that describes ``target`` exactly."""
    data = {
        "submitted_by": author,
        "priority": priority,
        "full_name": target.full_name,
        "roll_number": target.roll_number,
        "college": target.college,
        "course": target.course,
        "year": target.year,
        "section": target.section,
        "department": target.department,
        "nickname": target.nickname,
    }
    data.update(overrides)
    return CrushEntry.objects.create(**data)


def make_admin():
    return User.objects.create_superuser(
        username="verifier@x.edu", email="verifier@x.edu", password="admin-pass-123"
    )


def entry_payload(prefix, target, **overrides):
    data = {
        f"{prefix}-full_name": target.full_name,
        f"{prefix}-roll_number": target.roll_number,
        f"{prefix}-college": target.college_id,
        f"{prefix}-course": target.course,
        f"{prefix}-year": target.year,
        f"{prefix}-section": target.section,
        f"{prefix}-department": target.department,
        f"{prefix}-nickname": target.nickname,
    }
    data.update(overrides)
    return data


class NormalizationTests(TestCase):
    def test_roll_number_is_the_identity_key(self):
        self.assertEqual(normalize_roll_number(" 23bca-104 "), "23BCA104")

    def test_name_normalization_keeps_middle_initials(self):
        self.assertEqual(normalize_name("  Priya   K.   Sharma "), "PRIYA K SHARMA")

    def test_roll_number_is_unique_per_campus_but_not_globally(self):
        c1 = College.objects.create(name="ABC College")
        c2 = College.objects.create(name="XYZ University")
        make_student(c1, "23BCA104", "Aman")

        make_student(c2, "23bca104", "Twin")  # same roll, other campus: allowed
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_student(c1, "23BCA104", "Impostor")


class CrushEntryFormTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.me = make_student(self.college, "23BCA101", "Aman")
        self.target = make_student(self.college, "23BCA102", "Priya")

    def test_duplicate_person_across_slots_is_rejected(self):
        make_entry(self.me, self.target, priority=1)
        form = CrushEntryForm(
            entry_payload("crush2", self.target),
            author=self.me,
            priority=2,
            prefix="crush2",
        )
        self.assertFalse(form.is_valid())
        self.assertIn("roll_number", form.errors)

    def test_blank_optional_fields_are_allowed(self):
        form = CrushEntryForm(
            entry_payload(
                "crush1",
                self.target,
                **{
                    "crush1-section": "",
                    "crush1-department": "",
                    "crush1-nickname": "",
                },
            ),
            author=self.me,
            priority=1,
            prefix="crush1",
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_a_crush_cannot_be_entered_on_another_campus(self):
        other = College.objects.create(name="XYZ University")
        form = CrushEntryForm(
            entry_payload(
                "crush1",
                self.target,
                **{"crush1-college": other.pk},
            ),
            author=self.me,
            priority=1,
            prefix="crush1",
        )
        self.assertFalse(form.is_valid())
        self.assertIn("college", form.errors)


class CampusIdEditTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.me = make_student(self.college, "23BCA101", "Aman")
        self.other = make_student(self.college, "23BCA102", "Priya")
        self.client.force_login(self.me.user)

    def payload(self, **overrides):
        data = {
            "full_name": self.me.full_name,
            "roll_number": self.me.roll_number,
            "nickname": "",
            "course": self.me.course,
            "year": self.me.year,
            "section": self.me.section,
            "department": "",
            "gender": self.me.gender,
        }
        data.update(overrides)
        return data

    def test_roll_number_can_be_edited_and_is_normalized(self):
        response = self.client.post(
            reverse("campus:campus_id"),
            self.payload(roll_number=" 23bca-105 "),
        )
        self.assertRedirects(response, reverse("campus:campus_id"))
        self.me.refresh_from_db()
        self.assertEqual(self.me.roll_number, "23BCA-105")
        self.assertEqual(self.me.normalized_roll_number, "23BCA105")

    def test_roll_number_cannot_clash_with_another_student(self):
        response = self.client.post(
            reverse("campus:campus_id"),
            self.payload(roll_number=self.other.roll_number),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already registered at this campus")
        self.me.refresh_from_db()
        self.assertEqual(self.me.roll_number, "23BCA101")

    def test_changing_roll_number_clears_verification(self):
        self.me.is_verified = True
        self.me.save(update_fields=["is_verified"])

        self.client.post(
            reverse("campus:campus_id"), self.payload(roll_number="23BCA105")
        )
        self.me.refresh_from_db()
        self.assertFalse(self.me.is_verified)

    def test_editing_other_fields_keeps_verification(self):
        self.me.is_verified = True
        self.me.save(update_fields=["is_verified"])

        self.client.post(
            reverse("campus:campus_id"), self.payload(full_name="Aman K. Kumar")
        )
        self.me.refresh_from_db()
        self.assertTrue(self.me.is_verified)

    def test_profile_edit_refreshes_incoming_confidence(self):
        make_entry(self.other, self.me)
        seal_secret(self.other)
        proposal = PotentialMatch.objects.get(registered_student=self.me)
        before = proposal.confidence_score

        self.client.post(
            reverse("campus:campus_id"), self.payload(full_name="Aman K. Kumar")
        )
        proposal.refresh_from_db()
        self.assertLess(proposal.confidence_score, before)

    def test_profile_edit_that_breaks_identity_drops_pending_proposal(self):
        make_entry(self.other, self.me)
        seal_secret(self.other)
        self.assertEqual(PotentialMatch.objects.pending().count(), 1)

        self.client.post(reverse("campus:campus_id"), self.payload(course="BBA"))
        self.assertEqual(PotentialMatch.objects.pending().count(), 0)


class MatchingGateTests(TestCase):
    def setUp(self):
        self.c1 = College.objects.create(name="ABC College")
        self.c2 = College.objects.create(name="XYZ University")
        self.a = make_student(self.c1, "23BCA101", "Aman Kumar")
        self.b = make_student(self.c1, "23BCA102", "Priya Singh")

    def test_same_campus_and_roll_is_eligible(self):
        entry = make_entry(self.a, self.b)
        verdict = compare(entry, self.b)
        self.assertTrue(verdict.eligible, verdict.blockers)
        self.assertGreaterEqual(verdict.confidence, MIN_CONFIDENCE)

    def test_different_roll_number_is_never_eligible(self):
        entry = make_entry(self.a, self.b, roll_number="23BCA999")
        self.assertFalse(compare(entry, self.b).eligible)

    def test_different_campus_is_never_eligible(self):
        outsider = make_student(self.c2, "23BCA102", "Priya Singh")
        entry = make_entry(self.a, self.b)  # entry lives in c1
        verdict = compare(entry, outsider)  # outsider is in c2
        self.assertFalse(verdict.eligible)
        self.assertIn("different campus", verdict.blockers)

    def test_conflicting_course_disqualifies_even_with_same_roll(self):
        entry = make_entry(self.a, self.b, course="BBA")
        verdict = compare(entry, self.b)
        self.assertFalse(verdict.eligible)
        self.assertTrue(any("course" in note for note in verdict.blockers))

    def test_name_typo_does_not_break_identity(self):
        entry = make_entry(self.a, self.b, full_name="Prya Sing")
        verdict = compare(entry, self.b)
        self.assertTrue(verdict.eligible)
        self.assertGreaterEqual(verdict.confidence, MIN_CONFIDENCE)


class IdentityResolutionTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.me = make_student(self.college, "23BCA101", "Aman Kumar")
        self.target = make_student(self.college, "23BCA102", "Priya Sharma")
        self.admin = make_admin()

    def test_exact_roll_and_name_auto_resolves_with_audit(self):
        entry = make_entry(self.me, self.target)
        resolve_entry(entry)
        entry.refresh_from_db()

        self.assertEqual(entry.resolved_student, self.target)
        self.assertEqual(entry.identity_status, CrushEntry.ResolutionStatus.RESOLVED)
        self.assertTrue(entry.resolution_method.startswith("auto"))
        candidate = IdentityCandidate.objects.get(
            crush_entry=entry, candidate=self.target
        )
        self.assertEqual(candidate.status, IdentityCandidate.Status.CONFIRMED)
        self.assertTrue(
            IdentityResolutionAudit.objects.filter(
                crush_entry=entry,
                action=IdentityResolutionAudit.Action.AUTO_RESOLVED,
            ).exists()
        )

    def test_candidate_evidence_records_weighted_score_components(self):
        entry = make_entry(self.me, self.target)
        scored = score_candidate(entry, self.target)
        components = scored.evidence["components"]

        self.assertEqual(
            set(components),
            {"roll", "name", "nickname", "course", "year", "section", "department"},
        )
        self.assertAlmostEqual(sum(components.values()), scored.score, places=1)
        self.assertEqual(components["roll"], 45.0)
        self.assertEqual(components["name"], 30.0)

    def test_missing_roll_creates_candidate_but_never_auto_binds(self):
        entry = make_entry(self.me, self.target, roll_number="")
        resolve_entry(entry)
        entry.refresh_from_db()

        self.assertIsNone(entry.resolved_student)
        self.assertEqual(
            entry.identity_status, CrushEntry.ResolutionStatus.CANDIDATE_FOUND
        )
        self.assertTrue(
            IdentityCandidate.objects.filter(
                crush_entry=entry, candidate=self.target
            ).exists()
        )
        self.assertFalse(
            PotentialMatch.objects.filter(crush_entry=entry).exists()
        )

    def test_conflicting_roll_creates_review_candidate_but_never_binds(self):
        entry = make_entry(self.me, self.target, roll_number="WRONG-999")
        resolve_entry(entry)
        entry.refresh_from_db()
        candidate = IdentityCandidate.objects.get(
            crush_entry=entry, candidate=self.target
        )

        self.assertIsNone(entry.resolved_student)
        self.assertEqual(
            entry.identity_status, CrushEntry.ResolutionStatus.NEEDS_REVIEW
        )
        self.assertTrue(candidate.evidence["roll_conflict"])

    def test_late_registration_recovers_a_previous_entry_safely(self):
        typed_early = CrushEntry.objects.create(
            submitted_by=self.me,
            priority=1,
            full_name="Riya Verma",
            roll_number="23BCA777",
            college=self.college,
            course="BCA",
            year=2,
            section="A",
            department="",
        )
        resolve_entry(typed_early)
        typed_early.refresh_from_db()
        self.assertIsNone(typed_early.resolved_student)

        joined = make_student(self.college, "23BCA777", "Riya Verma")
        make_entry(joined, self.me)
        from .matching import match_new_student

        match_new_student(joined)
        typed_early.refresh_from_db()

        self.assertEqual(typed_early.resolved_student, joined)
        self.assertTrue(
            PotentialMatch.objects.filter(
                crush_entry=typed_early,
                registered_student=joined,
                status=PotentialMatch.Status.PENDING,
            ).exists()
        )

    def test_reviewer_confirmation_links_identity_and_queues_proposal(self):
        entry = make_entry(self.me, self.target, roll_number="")
        resolve_entry(entry)
        candidate = IdentityCandidate.objects.get(
            crush_entry=entry, candidate=self.target
        )

        confirm_candidate(candidate, self.admin, notes="Documents checked.")
        entry.refresh_from_db()
        candidate.refresh_from_db()

        self.assertEqual(entry.resolved_student, self.target)
        self.assertEqual(candidate.status, IdentityCandidate.Status.CONFIRMED)
        self.assertTrue(
            PotentialMatch.objects.filter(
                crush_entry=entry,
                registered_student=self.target,
                status=PotentialMatch.Status.PENDING,
            ).exists()
        )

    def test_rejecting_candidate_keeps_entry_unresolved(self):
        entry = make_entry(self.me, self.target, roll_number="")
        resolve_entry(entry)
        candidate = IdentityCandidate.objects.get(
            crush_entry=entry, candidate=self.target
        )

        reject_candidate(candidate, self.admin, notes="Not the same person.")
        entry.refresh_from_db()
        candidate.refresh_from_db()

        self.assertIsNone(entry.resolved_student)
        self.assertEqual(candidate.status, IdentityCandidate.Status.REJECTED)

        resolve_entry(entry, force=True)
        entry.refresh_from_db()
        candidate.refresh_from_db()
        self.assertIsNone(entry.resolved_student)
        self.assertEqual(candidate.status, IdentityCandidate.Status.REJECTED)

    def test_reopening_a_rejected_candidate_is_audited(self):
        entry = make_entry(self.me, self.target, roll_number="")
        resolve_entry(entry)
        candidate = IdentityCandidate.objects.get(
            crush_entry=entry, candidate=self.target
        )
        reject_candidate(candidate, self.admin, notes="Not enough evidence.")
        candidate.refresh_from_db()

        reopen_candidate(candidate, self.admin, notes="Student provided an ID.")
        candidate.refresh_from_db()

        self.assertEqual(candidate.status, IdentityCandidate.Status.NEEDS_REVIEW)
        self.assertTrue(
            IdentityResolutionAudit.objects.filter(
                crush_entry=entry,
                action=IdentityResolutionAudit.Action.REOPENED,
                candidate_to_status=IdentityCandidate.Status.NEEDS_REVIEW,
            ).exists()
        )

    def test_mark_unresolvable_preserves_entry_and_clears_pending_match(self):
        entry = make_entry(self.me, self.target)
        resolve_entry(entry)
        seal_secret(self.me)
        self.assertTrue(PotentialMatch.objects.filter(crush_entry=entry).exists())

        mark_unresolvable(entry, self.admin, notes="Person unidentifiable.")
        entry.refresh_from_db()

        self.assertTrue(entry.is_active)
        self.assertEqual(entry.identity_status, CrushEntry.ResolutionStatus.UNRESOLVABLE)
        self.assertIsNone(entry.resolved_student)
        self.assertFalse(
            PotentialMatch.objects.filter(
                crush_entry=entry, status=PotentialMatch.Status.PENDING
            ).exists()
        )

    def test_approval_refuses_entry_that_is_not_verified(self):
        make_entry(self.me, self.target)
        make_entry(self.target, self.me)
        seal_secret(self.me)
        seal_secret(self.target)
        proposal = pending_pairs()[0]["forward"]
        CrushEntry.objects.filter(pk=proposal.crush_entry_id).update(
            resolved_student=None,
            identity_status=CrushEntry.ResolutionStatus.NEEDS_REVIEW,
        )

        with self.assertRaises(ApprovalError):
            approve_potential_match(proposal, self.admin)
        self.assertEqual(MutualMatch.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)


class IdentityReviewAccessTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.me = make_student(self.college, "23BCA101", "Aman")
        self.target = make_student(self.college, "23BCA102", "Priya")
        make_entry(self.me, self.target, roll_number="")
        resolve_entry(CrushEntry.objects.get(submitted_by=self.me))

    def test_superuser_can_open_identity_review(self):
        admin = make_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse("campus:identity_review"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identity review")

    def test_plain_staff_without_identity_permission_is_redirected(self):
        staff = User.objects.create_user(
            username="staff@x.edu", email="staff@x.edu", password="x", is_staff=True
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("campus:identity_review"))
        self.assertEqual(response.status_code, 302)

    def test_superuser_can_confirm_from_review_desk(self):
        admin = make_admin()
        candidate = IdentityCandidate.objects.get(candidate=self.target)
        self.client.force_login(admin)
        response = self.client.post(
            reverse(
                "campus:identity_candidate_action",
                args=[candidate.pk, "confirm"],
            ),
            {"notes": "Verified against the campus ID card."},
        )
        self.assertEqual(response.status_code, 302)
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, IdentityCandidate.Status.CONFIRMED)


class ProposalTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.a = make_student(self.college, "23BCA101", "Aman")
        self.b = make_student(self.college, "23BCA102", "Priya")
        self.c = make_student(self.college, "23BCA103", "Rohan")

    def test_sealing_an_empty_list_is_refused(self):
        with self.assertRaises(SelectionError):
            seal_secret(self.a)

    def test_one_sided_entry_creates_a_pending_proposal_but_no_pair(self):
        make_entry(self.a, self.b)
        self.assertEqual(seal_secret(self.a), 1)
        self.assertEqual(PotentialMatch.objects.pending().count(), 1)
        self.assertEqual(pending_pairs(), [])

    def test_sealing_never_notifies_anyone(self):
        make_entry(self.a, self.b)
        make_entry(self.b, self.a)
        seal_secret(self.a)
        seal_secret(self.b)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(MutualMatch.objects.count(), 0)

    def test_reciprocal_entries_form_one_pending_pair(self):
        make_entry(self.a, self.b)
        make_entry(self.b, self.a)
        seal_secret(self.a)
        seal_secret(self.b)
        pairs = pending_pairs()
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["forward"].pair_key, pairs[0]["backward"].pair_key)

    def test_sealing_twice_does_not_duplicate_proposals(self):
        make_entry(self.a, self.b)
        seal_secret(self.a)
        self.assertEqual(seal_secret(self.a), 0)
        self.assertEqual(PotentialMatch.objects.count(), 1)

    def test_adding_reciprocal_entries_creates_a_pair_immediately(self):
        self.client.force_login(self.a.user)
        self.client.post(
            reverse("campus:add_crush_slot", args=[1]),
            entry_payload("crush1", self.b),
        )
        self.assertEqual(PotentialMatch.objects.pending().count(), 1)
        self.assertEqual(pending_pairs(), [])

        self.client.force_login(self.b.user)
        self.client.post(
            reverse("campus:add_crush_slot", args=[1]),
            entry_payload("crush1", self.a),
        )
        self.assertEqual(PotentialMatch.objects.pending().count(), 2)
        self.assertEqual(len(pending_pairs()), 1)
        self.assertEqual(Notification.objects.count(), 0)

    def test_editing_an_entry_re_runs_matching(self):
        entry = make_entry(self.a, self.b)
        make_entry(self.b, self.a)
        self.assertEqual(PotentialMatch.objects.count(), 0)

        self.client.force_login(self.a.user)
        response = self.client.post(
            reverse("campus:edit_crush", args=[entry.pk]),
            entry_payload("crush1", self.b),
        )
        self.assertRedirects(response, reverse("campus:secret"))
        self.assertEqual(len(pending_pairs()), 1)

    def test_editing_an_entry_refreshes_pending_confidence(self):
        entry = make_entry(self.a, self.b)
        seal_secret(self.a)
        proposal = PotentialMatch.objects.get(crush_entry=entry)
        proposal_pk = proposal.pk
        before = proposal.confidence_score

        self.client.force_login(self.a.user)
        self.client.post(
            reverse("campus:edit_crush", args=[entry.pk]),
            entry_payload("crush1", self.b, **{"crush1-full_name": "Priyaa"}),
        )
        proposal.refresh_from_db()
        self.assertEqual(proposal.pk, proposal_pk)
        self.assertLess(proposal.confidence_score, before)

    def test_entry_below_threshold_gains_a_proposal_when_edited_above_it(self):
        entry = make_entry(
            self.a, self.b, full_name="Someone Else", section=""
        )
        seal_secret(self.a)
        self.assertEqual(PotentialMatch.objects.pending().count(), 0)

        self.client.force_login(self.a.user)
        self.client.post(
            reverse("campus:edit_crush", args=[entry.pk]),
            entry_payload("crush1", self.b, **{"crush1-section": ""}),
        )
        proposal = PotentialMatch.objects.get(crush_entry=entry)
        self.assertGreaterEqual(proposal.confidence_score, MIN_CONFIDENCE)

    def test_editing_entry_to_another_student_replaces_the_proposal(self):
        entry = make_entry(self.a, self.b)
        seal_secret(self.a)
        self.assertTrue(
            PotentialMatch.objects.filter(
                crush_entry=entry, registered_student=self.b
            ).exists()
        )

        self.client.force_login(self.a.user)
        self.client.post(
            reverse("campus:edit_crush", args=[entry.pk]),
            entry_payload("crush1", self.c),
        )
        old = PotentialMatch.objects.get(
            crush_entry=entry, registered_student=self.b
        )
        self.assertEqual(old.status, PotentialMatch.Status.STALE)
        new = PotentialMatch.objects.get(
            crush_entry=entry, registered_student=self.c
        )
        self.assertEqual(new.status, PotentialMatch.Status.PENDING)

    def test_priority_range_is_enforced(self):
        entry = CrushEntry(
            submitted_by=self.a,
            priority=MAX_CRUSHES + 1,
            full_name="X",
            roll_number="1",
            college=self.college,
            course="BCA",
            year=2,
        )
        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_one_entry_per_slot(self):
        make_entry(self.a, self.b, priority=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_entry(self.a, self.c, priority=1)


class ApprovalTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.a = make_student(self.college, "23BCA101", "Aman")
        self.b = make_student(self.college, "23BCA102", "Priya")
        self.admin = make_admin()
        make_entry(self.a, self.b)
        make_entry(self.b, self.a)
        seal_secret(self.a)
        seal_secret(self.b)
        self.proposal = pending_pairs()[0]["forward"]

    def test_approval_creates_exactly_one_match_and_notifies_both(self):
        match = approve_potential_match(self.proposal, self.admin)
        self.assertEqual(MutualMatch.objects.count(), 1)
        self.assertEqual(match.pk, self.proposal.mutual_match_id)
        self.assertEqual(Notification.objects.filter(student=self.a).count(), 1)
        self.assertEqual(Notification.objects.filter(student=self.b).count(), 1)
        self.assertEqual(
            PotentialMatch.objects.pending().count(), 0
        )

    def test_approval_is_idempotent_for_a_pair(self):
        match = approve_potential_match(self.proposal, self.admin)
        self.assertIsNotNone(match.notified_at)
        notifications = Notification.objects.count()
        with self.assertRaises(ApprovalError):
            approve_potential_match(self.proposal, self.admin)
        self.assertEqual(MutualMatch.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), notifications)

    def test_editing_refreshes_score_without_undoing_approval(self):
        approve_potential_match(self.proposal, self.admin)
        entry = self.proposal.crush_entry
        before = self.proposal.confidence_score

        self.client.force_login(self.a.user)
        self.client.post(
            reverse("campus:edit_crush", args=[entry.pk]),
            entry_payload("crush1", self.b, **{"crush1-full_name": "Priyaa"}),
        )
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, PotentialMatch.Status.APPROVED)
        self.assertLess(self.proposal.confidence_score, before)
        self.assertEqual(MutualMatch.objects.count(), 1)

    def test_repointing_an_approved_entry_drops_its_stale_score(self):
        approve_potential_match(self.proposal, self.admin)
        entry = self.proposal.crush_entry
        other = make_student(self.college, "23BCA103", "Rohan")

        self.client.force_login(self.a.user)
        self.client.post(
            reverse("campus:edit_crush", args=[entry.pk]),
            entry_payload("crush1", other),
        )
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, PotentialMatch.Status.APPROVED)
        self.assertEqual(self.proposal.confidence_score, 0)
        self.assertIn("different roll number", self.proposal.match_reasons)
        self.assertEqual(MutualMatch.objects.count(), 1)

    def test_only_the_side_that_consented_reports_consent(self):
        match = approve_potential_match(self.proposal, self.admin)
        match.record_consent(self.a)
        match.save(update_fields=["user_a_consented", "user_b_consented"])

        self.assertTrue(match.has_consented(self.a))
        self.assertFalse(match.has_consented(self.b))

    def test_rejection_closes_both_halves_and_notifies_nobody(self):
        reject_potential_match(self.proposal, self.admin, admin_notes="not them")
        self.assertEqual(MutualMatch.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(
            PotentialMatch.objects.pending().count(), 0
        )
        self.assertEqual(
            PotentialMatch.objects.filter(status=PotentialMatch.Status.REJECTED).count(),
            2,
        )

    def test_one_sided_proposal_cannot_be_approved(self):
        outsider = make_student(self.college, "23BCA199", "Solo")
        make_entry(self.a, outsider, priority=2)
        seal_secret(self.a)
        solo = PotentialMatch.objects.pending().get(registered_student=outsider)
        with self.assertRaises(ApprovalError):
            approve_potential_match(solo, self.admin)

    def test_review_desk_requires_a_note_before_approving(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("campus:approve_match", args=[self.proposal.pk]),
            {},
        )
        self.assertRedirects(
            response,
            reverse("campus:pending_match_detail", args=[self.proposal.pk]),
        )
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, PotentialMatch.Status.PENDING)
        self.assertEqual(MutualMatch.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)


class PriorityPrivacyTests(TestCase):
    """Priority must never reach a student's browser (requirements 13/16)."""

    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.a = make_student(self.college, "23BCA101", "Aman")
        self.b = make_student(self.college, "23BCA102", "Priya")
        self.admin = make_admin()
        make_entry(self.a, self.b, priority=3)
        make_entry(self.b, self.a, priority=1)
        seal_secret(self.a)
        seal_secret(self.b)
        self.match = approve_potential_match(pending_pairs()[0]["forward"], self.admin)
        self.a.user.set_password("s3cret-pass-xyz")
        self.a.user.save()

    def test_public_payload_exposes_no_priority(self):
        payload = self.match.as_public_dict()
        self.assertEqual(payload, {"match": True, "status": "mutual"})
        self.assertNotIn("priority", payload)

    def test_secret_desk_never_prints_priority(self):
        self.client.force_login(self.a.user)
        html = self.client.get(reverse("campus:secret")).content.decode().lower()
        for leak in ("priority", "#1", "#2", "#3", "ranked"):
            self.assertNotIn(leak, html, f"leaked {leak!r}")

    def test_match_page_never_prints_priority(self):
        self.client.force_login(self.a.user)
        html = self.client.get(self.match.get_absolute_url()).content.decode().lower()
        for leak in ("priority", "#1", "#2", "#3", "their_priority"):
            self.assertNotIn(leak, html, f"leaked {leak!r}")

    def test_dashboard_never_prints_priority(self):
        self.client.force_login(self.a.user)
        html = self.client.get(reverse("campus:dashboard")).content.decode().lower()
        self.assertNotIn("priority", html)

    def test_staff_review_does_show_priority(self):
        self.client.force_login(self.admin)
        proposal = self.match.source_matches.first()
        html = self.client.get(
            reverse("campus:pending_match_detail", args=[proposal.pk])
        ).content.decode()
        self.assertIn("Internal priority", html)

    def test_full_roll_number_is_masked(self):
        self.assertEqual(self.a.masked_roll_number, "•••101")
        self.assertNotIn("23BCA101", self.a.masked_roll_number)


class StaffAccessTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.student = make_student(self.college, "23BCA101", "Aman")
        self.student.user.set_password("a-long-enough-pass")
        self.student.user.save()

    def test_plain_student_cannot_reach_the_review_desk(self):
        self.client.force_login(self.student.user)
        response = self.client.get(reverse("campus:pending_matches"))
        self.assertRedirects(response, reverse("campus:dashboard"))

    def test_superuser_can_reach_the_review_desk(self):
        admin = make_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse("campus:pending_matches"))
        self.assertEqual(response.status_code, 200)


class SeedMatchCommandTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.a = make_student(self.college, "23BCA104", "Aman Kumar")
        self.b = make_student(self.college, "23BCA107", "Priya Singh")

    def test_command_runs_the_full_verified_flow(self):
        make_admin()
        call_command("seed_match", stdout=StringIO())
        self.assertEqual(MutualMatch.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 2)

    def test_command_needs_a_verifier(self):
        with self.assertRaises(CommandError):
            call_command("seed_match", stdout=StringIO())


class FlowTests(TestCase):
    """The onboarding funnel and the manual crush flow."""

    def setUp(self):
        self.college = College.objects.create(name="ABC College", city="Patna")
        self.target = make_student(self.college, "23BCA107", "Priya Singh")

    def test_landing_is_public(self):
        response = self.client.get(reverse("campus:landing"))
        self.assertEqual(response.status_code, 200)

    def test_desk_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("campus:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_register_then_onboard_then_add_and_seal(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "email": "newbie@example.edu",
                "password1": "a-long-enough-pass-1",
                "password2": "a-long-enough-pass-1",
                "agree": "on",
            },
        )
        self.assertRedirects(response, reverse("campus:campus_select"))

        response = self.client.post(
            reverse("campus:campus_select"), {"college": self.college.pk}
        )
        self.assertRedirects(response, reverse("campus:identity"))

        response = self.client.post(
            reverse("campus:identity"),
            {
                "full_name": "Aman Kumar",
                "roll_number": "23BCA104",
                "course": "BCA",
                "year": 2,
                "section": "A",
                "gender": "male",
                "date_of_birth": "2005-05-05",
                "department": "",
                "nickname": "",
                "age_confirmation": "on",
            },
        )
        self.assertRedirects(response, reverse("campus:secret"))

        response = self.client.post(
            reverse("campus:add_crush_slot", args=[1]),
            entry_payload("crush1", self.target),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Priya Singh")

        response = self.client.post(reverse("campus:seal"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "campus/sealed.html")

    def test_cannot_enter_yourself(self):
        user = User.objects.create_user(
            username="self@x.edu", email="self@x.edu", password="pw-long-enough"
        )
        me = make_student(self.college, "23BCA201", "Myself")
        me.user = user
        me.save(update_fields=["user"])
        self.client.force_login(user)

        self.client.post(
            reverse("campus:add_crush_slot", args=[1]),
            entry_payload(
                "crush1",
                me,
                **{"crush1-roll_number": me.roll_number},
            ),
        )
        self.assertEqual(CrushEntry.objects.filter(submitted_by=me).count(), 0)

    def test_mark_read_ignores_an_external_next_url(self):
        me = make_student(self.college, "23BCA202", "Aman Kumar")
        note = Notification.objects.create(
            student=me,
            kind=Notification.Kind.REVEAL,
            message="Test notification",
            url="/matches/",
        )
        self.client.force_login(me.user)
        response = self.client.post(
            reverse("campus:mark_read", args=[note.pk]),
            {"next": "https://evil.example/phish"},
        )
        self.assertRedirects(response, reverse("campus:notifications"))

    def test_block_ignores_an_external_next_url(self):
        me = make_student(self.college, "23BCA203", "Aman Kumar")
        self.client.force_login(me.user)
        response = self.client.post(
            reverse("campus:block", args=[self.target.pk]),
            {"confirm": "on", "next": "https://evil.example/phish"},
        )
        self.assertRedirects(response, reverse("campus:matches"))


class CollegeCreateTests(TestCase):
    """A candidate can add a missing college; later candidates find it."""

    def test_add_college_creates_and_selects_it(self):
        response = self.client.post(
            reverse("campus:add_college"),
            {"name": "Ganga Devi Mahila College", "city": "Patna", "state": "Bihar"},
        )
        # Anonymous picker step: remember the campus, then continue to login.
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)
        college = College.objects.get(name="Ganga Devi Mahila College")
        self.assertTrue(college.is_active)
        self.assertEqual(self.client.session["campus_id"], college.pk)

    def test_added_college_appears_in_another_candidates_search(self):
        self.client.post(
            reverse("campus:add_college"),
            {"name": "Tilka Manjhi Bhagalpur University"},
        )
        fresh = Client()
        response = fresh.get(reverse("campus:campus_select"), {"q": "tilka manjhi"})
        self.assertContains(response, "Tilka Manjhi Bhagalpur University")

    def test_add_college_is_case_insensitively_deduplicated(self):
        existing = College.objects.create(name="ABC College", city="Patna")
        self.client.post(
            reverse("campus:add_college"),
            {"name": "  abc   college ", "state": "Bihar"},
        )
        self.assertEqual(College.objects.filter(name__iexact="abc college").count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.state, "Bihar")

    def test_blank_or_tiny_names_are_rejected(self):
        response = self.client.post(reverse("campus:add_college"), {"name": "ab"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "campus/campus_select.html")
        self.assertFalse(College.objects.filter(name="ab").exists())


class EveryPageSmokeTests(TestCase):
    """Every renderable route must return 200 for the right viewer."""

    def setUp(self):
        self.college = College.objects.create(name="ABC College", city="Patna")
        College.objects.create(name="XYZ University", city="Delhi")
        self.me = make_student(self.college, "23BCA101", "Aman Kumar")
        self.priya = make_student(self.college, "23BCA102", "Priya Singh")
        self.admin = make_admin()
        make_entry(self.me, self.priya)
        make_entry(self.priya, self.me)
        seal_secret(self.me)
        seal_secret(self.priya)
        self.proposal = pending_pairs()[0]["forward"]
        self.match = approve_potential_match(self.proposal, self.admin)
        self.me.user.set_password("a-long-enough-pass")
        self.me.user.save()

    def assertAllPagesLoad(self, pages):
        for url in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/html", response["Content-Type"])

    def test_seal_flow_renders_confirm_then_sealed_pages(self):
        self.client.force_login(self.me.user)
        confirm = self.client.get(reverse("campus:seal"))
        self.assertEqual(confirm.status_code, 200)
        self.assertTemplateUsed(confirm, "campus/seal_confirm.html")

        sealed = self.client.post(reverse("campus:seal"))
        self.assertEqual(sealed.status_code, 200)
        self.assertTemplateUsed(sealed, "campus/sealed.html")

    def test_every_page_as_signed_in_student(self):
        self.client.force_login(self.me.user)
        self.assertAllPagesLoad([
            reverse("campus:landing"),
            reverse("campus:secret"),
            reverse("campus:seal"),
            reverse("campus:dashboard"),
            reverse("campus:matches"),
            self.match.get_absolute_url(),
            reverse("campus:campus_id"),
            reverse("campus:privacy"),
            reverse("campus:notifications"),
            reverse("campus:invite"),
            reverse("core:about"),
            reverse("core:how_it_works"),
            reverse("core:privacy_policy"),
            reverse("core:terms"),
        ])

    def test_every_staff_page_as_verifier(self):
        self.client.force_login(self.admin)
        self.assertAllPagesLoad([
            reverse("campus:staff_dashboard"),
            reverse("campus:pending_matches"),
            reverse("campus:pending_match_detail", args=[self.proposal.pk]),
            reverse("campus:identity_review"),
            reverse(
                "campus:identity_review_detail",
                args=[self.proposal.crush_entry_id],
            ),
        ])

    def test_onboarding_pages_redirect_once_you_are_complete(self):
        self.client.force_login(self.me.user)
        for url in [
            reverse("campus:campus_select"),
            reverse("campus:identity"),
            reverse("accounts:login"),
            reverse("accounts:register"),
        ]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("campus:dashboard"), response.url)

    def test_every_public_page_as_anonymous(self):
        self.assertAllPagesLoad([
            reverse("campus:landing"),
            reverse("campus:campus_select"),
            f"{reverse('campus:campus_select')}?q=patna",
            reverse("campus:invite"),
            reverse("core:about"),
            reverse("core:how_it_works"),
            reverse("core:privacy_policy"),
            reverse("core:terms"),
            reverse("accounts:login"),
            reverse("accounts:register"),
            reverse("accounts:forgot_password"),
            reverse("accounts:forgot_password_done"),
            reverse("accounts:password_reset_complete"),
        ])

    def test_onboarding_pages_render_for_a_half_signed_in_user(self):
        user = User.objects.create_user(
            username="half@b.edu", email="half@b.edu", password="pw-long-enough"
        )
        self.client.force_login(user)
        self.assertAllPagesLoad([reverse("campus:campus_select")])

        self.client.post(reverse("campus:campus_select"), {"college": self.college.pk})
        self.assertAllPagesLoad([reverse("campus:identity")])

    def test_revealed_match_page_loads(self):
        match = self.match
        match.record_consent(self.me)
        match.record_consent(self.priya)
        match.sync_status()
        self.client.force_login(self.me.user)
        response = self.client.get(match.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Priya Singh")

    def test_secret_desk_has_no_student_search(self):
        self.client.force_login(self.me.user)
        html = self.client.get(reverse("campus:secret")).content.decode().lower()
        self.assertNotIn("search your campus", html)
        self.assertNotIn("search_students", html)

    def test_no_page_uses_a_horizontal_table_or_scroll_region(self):
        """Student pages must stay narrow-screen friendly."""
        self.client.force_login(self.me.user)
        for url in [
            reverse("campus:landing"),
            reverse("campus:secret"),
            reverse("campus:dashboard"),
        ]:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotIn("<table", html)
                self.assertNotIn("min-width: 6", html)

    def test_error_pages_render(self):
        self.assertEqual(self.client.get("/definitely-not-a-page/").status_code, 404)

    def test_sitemap_and_robots_are_servable(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        xml = response.content.decode()
        self.assertIn("<urlset", xml)
        self.assertIn("/how-it-works/", xml)

    def test_sitemap_uses_the_real_site_url_not_example_com(self):
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn("example.com", xml)
        self.assertIn(settings.SITE_URL, xml)

    def test_sitemap_never_leaks_campus_or_student_pages(self):
        """No campus directory and no private or staff routes may be indexed."""
        xml = self.client.get("/sitemap.xml").content.decode()
        for leak in [
            "/matches/",
            "/desk/",
            "/secret/",
            "/campus-id/",
            "/notifications/",
            "/identity/",
            "/staff/",
        ]:
            with self.subTest(leak=leak):
                self.assertNotIn(f"<loc>{leak}", xml)
        for college in College.objects.all():
            with self.subTest(college=college.name):
                self.assertNotIn(college.name, xml)

    def test_robots_txt_points_at_the_sitemap(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("Sitemap:", body)
        for blocked in ["/desk/", "/secret/", "/matches/", "/notifications/"]:
            with self.subTest(blocked=blocked):
                self.assertIn(f"Disallow: {blocked}", body)


class CollegeGrowthTests(TestCase):
    """Shareable college landing + join links (growth)."""

    def setUp(self):
        self.college = College.objects.create(
            name="Tilka Manjhi Bhagalpur University"
        )

    def test_slug_is_derived_from_name(self):
        self.assertTrue(self.college.slug)
        self.assertIn("tilka-manjhi", self.college.slug)

    def test_slug_stays_unique_across_similar_names(self):
        other = College.objects.create(name="Tilka Manjhi Bhagalpur University 2")
        self.assertNotEqual(other.slug, self.college.slug)

    def test_landing_shows_college_but_no_student_directory(self):
        response = self.client.get(reverse("campus:college_landing", args=[self.college.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.college.name)
        self.assertNotContains(response, "StudentProfile")

    def test_landing_is_noindex_while_thin(self):
        response = self.client.get(reverse("campus:college_landing", args=[self.college.slug]))
        self.assertContains(response, "noindex,nofollow")

    def test_landing_is_indexable_after_traction(self):
        make_student(self.college, "24abc001")
        make_student(self.college, "24abc002")
        make_student(self.college, "24abc003")
        make_student(self.college, "24abc004")
        make_student(self.college, "24abc005")
        response = self.client.get(reverse("campus:college_landing", args=[self.college.slug]))
        self.assertContains(response, "index,follow")

    def test_unknown_college_is_404(self):
        response = self.client.get(reverse("campus:college_landing", args=["nope"]))
        self.assertEqual(response.status_code, 404)

    def test_join_preselects_campus_for_anonymous_user(self):
        response = self.client.get(reverse("campus:join", args=[self.college.slug]))
        self.assertRedirects(response, reverse("accounts:register"))
        self.assertEqual(self.client.session.get("campus_id"), self.college.pk)

    def test_join_for_new_authenticated_user_goes_to_identity(self):
        user = User.objects.create_user(
            username="new@example.edu", email="new@example.edu", password="x"
        )
        self.client.force_login(user)
        response = self.client.get(reverse("campus:join", args=[self.college.slug]))
        self.assertRedirects(response, reverse("campus:identity"))

    def test_join_for_existing_student_goes_to_dashboard(self):
        student = make_student(self.college, "24abc099")
        self.client.force_login(student.user)
        response = self.client.get(reverse("campus:join", args=[self.college.slug]))
        self.assertRedirects(response, reverse("campus:dashboard"))

    def test_landing_does_not_index_college_slugs(self):
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn(f"/college/{self.college.slug}", xml)


class StaffDashboardTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.a = make_student(self.college, "23BCA101", "Aman")
        self.b = make_student(self.college, "23BCA102", "Priya")
        self.c = make_student(self.college, "23BCA103", "Rohan")
        self.d = make_student(self.college, "23BCA104", "Neha")
        self.e = make_student(self.college, "23BCA105", "Kabir")
        self.f = make_student(self.college, "23BCA106", "Isha")
        self.admin = make_admin()

        make_entry(self.a, self.b)
        make_entry(self.b, self.a)
        seal_secret(self.a)
        seal_secret(self.b)
        Block.objects.create(blocker=self.a, blocked=self.b)

        stale_entry = make_entry(self.c, self.d)
        PotentialMatch.objects.create(
            crush_entry=stale_entry,
            registered_student=self.d,
            status=PotentialMatch.Status.STALE,
            invalidated_reason="Entry was edited.",
        )

        self.identity_entry = make_entry(self.e, self.f, roll_number="")
        self.identity_entry.identity_status = (
            CrushEntry.ResolutionStatus.NEEDS_REVIEW
        )
        self.identity_entry.save(update_fields=["identity_status"])
        IdentityCandidate.objects.create(
            crush_entry=self.identity_entry,
            candidate=self.f,
            status=IdentityCandidate.Status.NEEDS_REVIEW,
            confidence_score=70,
            name_similarity=0.91,
            evidence={"reasons": ["name similar"], "conflicts": []},
        )
        CrushEntry.objects.exclude(pk=self.identity_entry.pk).update(
            identity_status=CrushEntry.ResolutionStatus.RESOLVED
        )

    def test_dashboard_counts_both_queues(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("campus:staff_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pending_pair_count"], 1)
        self.assertEqual(response.context["blocked_pair_count"], 1)
        self.assertEqual(response.context["stale_count"], 1)
        self.assertEqual(response.context["identity_review_count"], 1)
        self.assertEqual(response.context["unresolved_identity_count"], 1)
        self.assertContains(response, "Reciprocal queue")
        self.assertContains(response, "Ambiguous entries")

    def test_identity_only_staff_see_only_the_identity_desk(self):
        staff = User.objects.create_user(
            username="identity@x.edu",
            email="identity@x.edu",
            password="x",
            is_staff=True,
        )
        staff.user_permissions.add(
            Permission.objects.get(codename="review_identitycandidate")
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("campus:staff_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_review_identities"])
        self.assertFalse(response.context["can_verify_matches"])
        self.assertContains(response, "Ambiguous entries")
        self.assertNotContains(response, "Reciprocal queue")

    def test_plain_staff_without_review_permissions_is_redirected(self):
        staff = User.objects.create_user(
            username="plain@x.edu",
            email="plain@x.edu",
            password="x",
            is_staff=True,
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("campus:staff_dashboard"))
        self.assertEqual(response.status_code, 302)


class StaffMatchQueueTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.other = College.objects.create(name="XYZ University")
        self.a = make_student(self.college, "23BCA101", "Aman")
        self.b = make_student(self.college, "23BCA102", "Priya")
        self.c = make_student(self.other, "23XYZ201", "Rohan")
        self.d = make_student(self.other, "23XYZ202", "Neha")
        make_entry(self.a, self.b)
        make_entry(self.b, self.a)
        make_entry(self.c, self.d)
        make_entry(self.d, self.c)
        for student in [self.a, self.b, self.c, self.d]:
            seal_secret(student)
        Block.objects.create(blocker=self.a, blocked=self.b)
        self.admin = make_admin()

    def test_search_filters_by_either_direction(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("campus:pending_matches"), {"q": "Aman"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_pair_count"], 2)
        self.assertEqual(response.context["pair_count"], 1)
        self.assertEqual(len(response.context["pairs"]), 1)

    def test_blocked_filter_and_campus_filter(self):
        self.client.force_login(self.admin)
        blocked = self.client.get(
            reverse("campus:pending_matches"), {"blocked": "1"}
        )
        self.assertEqual(blocked.context["pair_count"], 1)
        self.assertTrue(blocked.context["pairs"][0]["is_blocked"])

        campus = self.client.get(
            reverse("campus:pending_matches"), {"college": self.other.pk}
        )
        self.assertEqual(campus.context["pair_count"], 1)
        self.assertEqual(
            campus.context["pairs"][0]["forward"].crush_entry.college_id,
            self.other.pk,
        )

    def test_one_sided_proposals_are_paginated(self):
        for index in range(21):
            student = make_student(
                self.other, f"23XYZ{300 + index}", f"Reviewer {index}"
            )
            make_entry(student, self.c)
            seal_secret(student)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("campus:pending_matches"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["unpaired_count"], 21)
        self.assertEqual(len(response.context["unpaired"]), 20)
        self.assertEqual(
            response.context["unpaired_page_obj"].paginator.num_pages, 2
        )

        second = self.client.get(reverse("campus:pending_matches"), {"upage": 2})
        self.assertEqual(len(second.context["unpaired"]), 1)

    def test_sort_and_pagination_parameters_are_safe(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("campus:pending_matches"),
            {"sort": "oldest", "page": "999"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sort"], "oldest")
        self.assertEqual(response.context["page_obj"].number, 1)


class StaffIdentityQueueTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.me = make_student(self.college, "23BCA101", "Aman")
        self.target = make_student(self.college, "23BCA102", "Priya")
        self.other = make_student(self.college, "23BCA103", "Rohan")
        self.entry = make_entry(self.me, self.target, roll_number="")
        self.entry.identity_status = CrushEntry.ResolutionStatus.NEEDS_REVIEW
        self.entry.save(update_fields=["identity_status"])
        self.candidate = IdentityCandidate.objects.create(
            crush_entry=self.entry,
            candidate=self.target,
            status=IdentityCandidate.Status.NEEDS_REVIEW,
            confidence_score=72,
            name_similarity=0.9,
            evidence={"reasons": ["name matches"], "conflicts": []},
        )
        self.conflict = IdentityCandidate.objects.create(
            crush_entry=self.entry,
            candidate=self.other,
            status=IdentityCandidate.Status.CANDIDATE,
            confidence_score=55,
            name_similarity=0.71,
            evidence={
                "reasons": ["name similar"],
                "conflicts": ["roll number differs"],
                "roll_conflict": True,
            },
        )
        Block.objects.create(blocker=self.me, blocked=self.other)
        self.admin = make_admin()

    def test_identity_filters_and_counts(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("campus:identity_review"), {"status": "needs_review"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["entry_count"], 1)
        self.assertEqual(response.context["status_counts"]["needs_review"], 1)
        self.assertContains(response, "Priya")

        search = self.client.get(
            reverse("campus:identity_review"), {"q": "Aman"}
        )
        self.assertEqual(search.context["entry_count"], 1)

        empty = self.client.get(
            reverse("campus:identity_review"), {"q": "Nobody Here"}
        )
        self.assertEqual(empty.context["entry_count"], 0)

    def test_candidate_selection_shows_conflicts_and_blocks(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("campus:identity_review_detail", args=[self.entry.pk]),
            {"candidate": self.conflict.pk},
        )
        self.assertEqual(response.status_code, 200)
        selected = response.context["selected_candidate"]
        self.assertEqual(selected.pk, self.conflict.pk)
        self.assertTrue(selected.hard_conflict)
        self.assertTrue(selected.is_blocked)
        self.assertFalse(selected.is_eligible)
        self.assertContains(response, "A block exists")
        self.assertContains(response, "ROLL CONFLICT")
        self.assertContains(response, f"?candidate={self.candidate.pk}")

    def test_detail_renders_weighted_score_breakdown(self):
        self.candidate.evidence = {
            "reasons": ["name matches"],
            "conflicts": [],
            "score": 72,
            "components": {
                "roll": 45,
                "name": 20,
                "nickname": 0,
                "course": 4,
                "year": 3,
                "section": 0,
                "department": 0,
            },
        }
        self.candidate.save(update_fields=["evidence"])
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("campus:identity_review_detail", args=[self.entry.pk]),
            {"candidate": self.candidate.pk},
        )

        self.assertContains(response, "Score breakdown")
        self.assertContains(response, "Roll number")
        self.assertContains(response, "45.0 / 45")
        self.assertContains(response, "20.0 / 30")

    def test_bulk_rerun_is_post_only_and_audited(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("campus:identity_bulk_action"))
        self.assertEqual(response.status_code, 405)

        response = self.client.post(
            reverse("campus:identity_bulk_action"),
            {"action": "rerun", "entry_ids": [self.entry.pk]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            IdentityResolutionAudit.objects.filter(
                crush_entry=self.entry,
                action=IdentityResolutionAudit.Action.REOPENED,
            ).exists()
        )

    def test_bulk_rerun_requires_identity_permission(self):
        staff = User.objects.create_user(
            username="plain@x.edu",
            email="plain@x.edu",
            password="x",
            is_staff=True,
        )
        self.client.force_login(staff)
        response = self.client.post(
            reverse("campus:identity_bulk_action"),
            {"action": "rerun", "entry_ids": [self.entry.pk]},
        )
        self.assertEqual(response.status_code, 302)
        self.entry.refresh_from_db()
        self.assertEqual(
            self.entry.identity_status,
            CrushEntry.ResolutionStatus.NEEDS_REVIEW,
        )


class StaffWorkflowEndToEndTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.a = make_student(self.college, "23BCA101", "Aman")
        self.b = make_student(self.college, "23BCA102", "Priya")
        self.entry_a = make_entry(self.a, self.b, roll_number="")
        self.entry_b = make_entry(self.b, self.a, roll_number="")
        resolve_entry(self.entry_a)
        resolve_entry(self.entry_b)
        seal_secret(self.a)
        seal_secret(self.b)
        self.admin = make_admin()

    def test_staff_can_resolve_identities_and_approve_the_match(self):
        self.client.force_login(self.admin)

        dashboard = self.client.get(reverse("campus:staff_dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.context["unresolved_identity_count"], 2)

        queue = self.client.get(reverse("campus:identity_review"))
        self.assertEqual(queue.status_code, 200)
        self.assertEqual(queue.context["entry_count"], 2)

        for entry, target in [(self.entry_a, self.b), (self.entry_b, self.a)]:
            candidate = IdentityCandidate.objects.get(
                crush_entry=entry, candidate=target
            )
            response = self.client.post(
                reverse(
                    "campus:identity_candidate_action",
                    args=[candidate.pk, "confirm"],
                ),
                {"notes": "Checked the campus record."},
            )
            self.assertEqual(response.status_code, 302)

        self.assertEqual(
            PotentialMatch.objects.filter(
                status=PotentialMatch.Status.PENDING
            ).count(),
            2,
        )

        match_queue = self.client.get(reverse("campus:pending_matches"))
        self.assertEqual(match_queue.status_code, 200)
        self.assertEqual(match_queue.context["pair_count"], 1)

        proposal = PotentialMatch.objects.pending().first()
        detail = self.client.get(
            reverse("campus:pending_match_detail", args=[proposal.pk])
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Approve match")

        approved = self.client.post(
            reverse("campus:approve_match", args=[proposal.pk]),
            {"admin_notes": "Both entries and identities verified."},
        )
        self.assertEqual(approved.status_code, 302)
        self.assertEqual(MutualMatch.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 2)


class StaffMatchDecisionTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="ABC College")
        self.a = make_student(self.college, "23BCA101", "Aman")
        self.b = make_student(self.college, "23BCA102", "Priya")
        make_entry(self.a, self.b)
        make_entry(self.b, self.a)
        seal_secret(self.a)
        seal_secret(self.b)
        self.proposal = PotentialMatch.objects.pending().first()
        self.admin = make_admin()

    @patch("campus.views.reconcile_all_matches")
    def test_reconcile_requires_match_review_permission(self, reconcile):
        staff = User.objects.create_user(
            username="identity@x.edu",
            email="identity@x.edu",
            password="x",
            is_staff=True,
        )
        staff.user_permissions.add(
            Permission.objects.get(codename="review_identitycandidate")
        )
        self.client.force_login(staff)

        response = self.client.post(reverse("campus:reconcile"))

        self.assertEqual(response.status_code, 302)
        reconcile.assert_not_called()

    def test_blocked_detail_disables_approval(self):
        Block.objects.create(blocker=self.b, blocked=self.a)
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("campus:pending_match_detail", args=[self.proposal.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["blocked"])
        self.assertFalse(response.context["can_approve"])
        self.assertContains(response, "A block exists")
        self.assertContains(response, "Approve match")

    def test_decided_proposal_has_no_decision_actions(self):
        reject_potential_match(
            self.proposal, self.admin, admin_notes="Identity evidence conflicted."
        )
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("campus:pending_match_detail", args=[self.proposal.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_approve"])
        self.assertContains(response, "Decision history")
        self.assertNotContains(response, "Approve match")
        self.assertNotContains(response, "Reject match")
