"""Production regression coverage for identity, matching, privacy and mail."""

from __future__ import annotations

from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.emails import deliver_verification_email, send_verification_email

from .forms import CrushEntryForm
from .identity_resolution import (
    IDENTITY_SCORING_VERSION,
    IdentityResolutionError,
    bind_identity,
    confirm_candidate,
    generate_candidates,
    mark_unresolvable,
    refresh_for_student,
    reject_candidate,
    reopen_candidate,
    resolve_entry,
)
from .matching import (
    MATCH_SCORING_VERSION,
    compare,
    match_entries_for,
    match_new_student,
    pending_pairs,
    propose_for_entry,
)
from .models import (
    Block,
    College,
    CrushEntry,
    IdentityCandidate,
    IdentityResolutionAudit,
    MutualMatch,
    Notification,
    PotentialMatch,
    Report,
    StudentProfile,
)
from .services import (
    ApprovalError,
    approve_potential_match,
    reject_potential_match,
    seal_secret,
)
from .tests import entry_payload, make_admin, make_entry, make_student
from .identity_resolution import retire_entry

User = get_user_model()


def repoint(entry: CrushEntry, target: StudentProfile) -> CrushEntry:
    entry.full_name = target.full_name
    entry.roll_number = target.roll_number
    entry.college = target.college
    entry.course = target.course
    entry.year = target.year
    entry.section = target.section
    entry.department = target.department
    entry.nickname = target.nickname
    entry.save()
    return entry


class IdentityResolutionRegressionTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="Regression College")
        self.author = make_student(self.college, "R001", "Alice Author")
        self.target = make_student(self.college, "R002", "Bob Target")

    def test_exact_campus_roll_and_name_auto_resolves(self):
        entry = make_entry(self.author, self.target)
        resolve_entry(entry)
        entry.refresh_from_db()

        self.assertEqual(entry.identity_status, CrushEntry.ResolutionStatus.RESOLVED)
        self.assertEqual(entry.resolved_student_id, self.target.pk)
        self.assertEqual(entry.resolution_method, "auto_exact_roll")
        self.assertEqual(entry.resolution_scoring_version, IDENTITY_SCORING_VERSION)

        candidate = IdentityCandidate.objects.get(
            crush_entry=entry, candidate=self.target
        )
        self.assertEqual(candidate.status, IdentityCandidate.Status.CONFIRMED)
        self.assertEqual(candidate.scoring_version, IDENTITY_SCORING_VERSION)
        self.assertTrue(candidate.evidence["roll_exact"])
        self.assertEqual(candidate.evidence["components"]["roll"], 45.0)
        self.assertEqual(
            IdentityResolutionAudit.objects.filter(
                crush_entry=entry,
                action=IdentityResolutionAudit.Action.AUTO_RESOLVED,
            ).count(),
            1,
        )

    def test_roll_number_alone_never_binds(self):
        entry = make_entry(self.author, self.target, full_name="Zzz Qqq")
        resolve_entry(entry)
        entry.refresh_from_db()

        self.assertIsNone(entry.resolved_student_id)
        self.assertEqual(entry.identity_status, CrushEntry.ResolutionStatus.NEEDS_REVIEW)
        self.assertFalse(
            IdentityResolutionAudit.objects.filter(
                crush_entry=entry,
                action=IdentityResolutionAudit.Action.AUTO_RESOLVED,
            ).exists()
        )

    def test_name_only_entry_becomes_candidate_not_link(self):
        entry = make_entry(self.author, self.target, roll_number="")
        resolve_entry(entry)
        entry.refresh_from_db()

        self.assertIsNone(entry.resolved_student_id)
        self.assertEqual(
            entry.identity_status, CrushEntry.ResolutionStatus.CANDIDATE_FOUND
        )
        self.assertTrue(
            IdentityCandidate.objects.filter(
                crush_entry=entry, candidate=self.target
            ).exists()
        )

    def test_cross_campus_identity_never_binds(self):
        other = College.objects.create(name="Other College")
        outsider = make_student(other, "X900", "Cara Outsider")
        entry = make_entry(self.author, outsider, college=self.college)

        resolve_entry(entry)
        entry.refresh_from_db()

        self.assertIsNone(entry.resolved_student_id)
        self.assertNotEqual(entry.resolved_student_id, outsider.pk)

    def test_submitter_from_another_campus_never_binds_local_student(self):
        other = College.objects.create(name="Remote College")
        remote_author = make_student(other, "X901", "Uma Outsider")
        local_target = make_student(self.college, "R003", "Local Target")
        entry = make_entry(remote_author, local_target)

        self.assertEqual(entry.college_id, local_target.college_id)
        self.assertNotEqual(entry.college_id, remote_author.college_id)

        resolve_entry(entry)
        entry.refresh_from_db()

        self.assertIsNone(entry.resolved_student_id)
        self.assertEqual(entry.identity_status, CrushEntry.ResolutionStatus.PENDING)
        self.assertFalse(
            IdentityResolutionAudit.objects.filter(
                crush_entry=entry,
                action=IdentityResolutionAudit.Action.AUTO_RESOLVED,
            ).exists()
        )

    def test_name_correction_keeps_auto_verified_link(self):
        entry = make_entry(self.author, self.target)
        resolve_entry(entry)
        entry.refresh_from_db()
        self.assertEqual(entry.resolved_student_id, self.target.pk)

        self.target.full_name = "Robert Xavier"
        self.target.save(update_fields=["full_name"])

        resolve_entry(entry)
        entry.refresh_from_db()

        self.assertEqual(entry.resolved_student_id, self.target.pk)
        self.assertEqual(entry.identity_status, CrushEntry.ResolutionStatus.RESOLVED)
        self.assertEqual(entry.resolution_method, "auto_exact_roll")

    def test_profile_name_edit_via_refresh_keeps_auto_verified_link(self):
        entry = make_entry(self.author, self.target)
        resolve_entry(entry)

        self.target.full_name = "Robert Xavier"
        self.target.save(update_fields=["full_name"])
        refresh_for_student(self.target)

        entry.refresh_from_db()
        self.assertEqual(entry.resolved_student_id, self.target.pk)
        self.assertEqual(entry.identity_status, CrushEntry.ResolutionStatus.RESOLVED)

    def test_profile_roll_change_invalidates_link_and_stales_proposal(self):
        entry = make_entry(self.author, self.target)
        resolve_entry(entry)
        propose_for_entry(entry)
        proposal = PotentialMatch.objects.get(crush_entry=entry)
        self.assertEqual(proposal.status, PotentialMatch.Status.PENDING)

        self.target.roll_number = "R999"
        self.target.save(update_fields=["roll_number"])
        refresh_for_student(self.target)

        entry.refresh_from_db()
        proposal.refresh_from_db()
        self.assertIsNone(entry.resolved_student_id)
        self.assertEqual(proposal.status, PotentialMatch.Status.STALE)

    def test_profile_change_stales_pending_proposal_without_verified_link(self):
        entry = make_entry(self.author, self.target, full_name="Zzz Qqq")
        resolve_entry(entry)
        propose_for_entry(entry)
        proposal = PotentialMatch.objects.get(crush_entry=entry)
        self.assertIsNone(entry.resolved_student_id)
        self.assertEqual(proposal.status, PotentialMatch.Status.PENDING)

        self.target.full_name = "Completely Different Person"
        self.target.roll_number = "R999"
        self.target.save(update_fields=["full_name", "roll_number"])
        refresh_for_student(self.target)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, PotentialMatch.Status.STALE)

    def test_manual_confirmation_survives_profile_roll_change(self):
        entry = make_entry(self.author, self.target, full_name="Zzz Qqq")
        resolve_entry(entry)
        candidate = IdentityCandidate.objects.get(
            crush_entry=entry, candidate=self.target
        )
        confirm_candidate(candidate, make_admin(), notes="Staff verified")

        self.target.full_name = "Renamed Person"
        self.target.roll_number = "R999"
        self.target.save(update_fields=["full_name", "roll_number"])
        refresh_for_student(self.target)

        entry.refresh_from_db()
        self.assertEqual(entry.resolved_student_id, self.target.pk)
        self.assertEqual(entry.resolution_method, "admin_confirmed")

    def test_rejected_candidate_is_sticky_across_resolution(self):
        entry = make_entry(self.author, self.target, full_name="Zzz Qqq")
        resolve_entry(entry)
        candidate = IdentityCandidate.objects.get(
            crush_entry=entry, candidate=self.target
        )
        admin = make_admin()
        reject_candidate(candidate, admin, notes="Not this person")

        resolve_entry(entry)
        entry.refresh_from_db()
        candidate.refresh_from_db()

        self.assertIsNone(entry.resolved_student_id)
        self.assertEqual(candidate.status, IdentityCandidate.Status.REJECTED)

    def test_rejected_candidate_requires_explicit_reopen_before_confirm(self):
        entry = make_entry(self.author, self.target, full_name="Zzz Qqq")
        resolve_entry(entry)
        candidate = IdentityCandidate.objects.get(
            crush_entry=entry, candidate=self.target
        )
        admin = make_admin()
        reject_candidate(candidate, admin)

        with self.assertRaises(IdentityResolutionError):
            confirm_candidate(candidate, admin)

        reopen_candidate(candidate, admin, notes="Recheck")
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, IdentityCandidate.Status.NEEDS_REVIEW)

        confirm_candidate(candidate, admin, notes="Verified manually")
        entry.refresh_from_db()
        self.assertEqual(entry.resolved_student_id, self.target.pk)
        self.assertEqual(entry.resolution_method, "admin_confirmed")

    def test_manual_confirmation_survives_rescoring(self):
        entry = make_entry(self.author, self.target, full_name="Zzz Qqq")
        resolve_entry(entry)
        candidate = IdentityCandidate.objects.get(
            crush_entry=entry, candidate=self.target
        )
        admin = make_admin()
        confirm_candidate(candidate, admin, notes="Staff verified")

        resolve_entry(entry, force=True)
        entry.refresh_from_db()

        self.assertEqual(entry.resolved_student_id, self.target.pk)
        self.assertEqual(entry.resolution_method, "admin_confirmed")

    def test_binding_is_idempotent(self):
        entry = make_entry(self.author, self.target)
        resolve_entry(entry)
        bind_identity(
            entry, self.target, method="auto_exact_roll", confidence=88.2
        )
        bind_identity(
            entry, self.target, method="auto_exact_roll", confidence=88.2
        )

        self.assertEqual(
            IdentityResolutionAudit.objects.filter(
                crush_entry=entry,
                action=IdentityResolutionAudit.Action.AUTO_RESOLVED,
            ).count(),
            1,
        )
        self.assertEqual(
            IdentityCandidate.objects.filter(
                crush_entry=entry,
                candidate=self.target,
                status=IdentityCandidate.Status.CONFIRMED,
            ).count(),
            1,
        )

    def test_self_binding_is_refused(self):
        entry = make_entry(self.author, self.target)
        with self.assertRaises(IdentityResolutionError):
            bind_identity(entry, self.author, method="manual", confidence=99)

    def test_blocked_identity_binding_is_refused(self):
        entry = make_entry(self.author, self.target)
        Block.objects.create(blocker=self.author, blocked=self.target)
        with self.assertRaises(IdentityResolutionError):
            bind_identity(entry, self.target, method="manual", confidence=99)

    def test_mark_unresolvable_is_sticky_and_retires_proposals(self):
        entry = make_entry(self.author, self.target)
        propose_for_entry(entry)
        proposal = PotentialMatch.objects.get(crush_entry=entry)
        admin = make_admin()

        mark_unresolvable(entry, admin, notes="Person left campus")
        entry.refresh_from_db()
        proposal.refresh_from_db()

        self.assertEqual(
            entry.identity_status, CrushEntry.ResolutionStatus.UNRESOLVABLE
        )
        self.assertIsNone(entry.resolved_student_id)
        self.assertEqual(proposal.status, PotentialMatch.Status.STALE)

        resolve_entry(entry)
        entry.refresh_from_db()
        self.assertEqual(
            entry.identity_status, CrushEntry.ResolutionStatus.UNRESOLVABLE
        )

    def test_deleting_student_releases_verified_link(self):
        entry = make_entry(self.author, self.target)
        resolve_entry(entry)
        entry.refresh_from_db()
        self.assertEqual(entry.resolved_student_id, self.target.pk)

        self.target.delete()
        entry.refresh_from_db()

        self.assertEqual(entry.identity_status, CrushEntry.ResolutionStatus.PENDING)
        self.assertIsNone(entry.resolved_student_id)
        self.assertIn("deleted", entry.resolution_notes.lower())


class IndependentEntryRegressionTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="Independent College")
        self.author = make_student(self.college, "A001", "Alice Author")
        self.targets = [
            make_student(self.college, "T101", "Target One"),
            make_student(self.college, "T102", "Target Two"),
            make_student(self.college, "T103", "Target Three"),
        ]

    def test_three_slots_resolve_independently(self):
        entries = [
            make_entry(self.author, target, priority=index)
            for index, target in enumerate(self.targets, start=1)
        ]

        match_entries_for(self.author)

        for entry, target in zip(entries, self.targets):
            entry.refresh_from_db()
            self.assertEqual(entry.resolved_student_id, target.pk)
            proposal = PotentialMatch.objects.get(crush_entry=entry)
            self.assertEqual(proposal.registered_student_id, target.pk)

        self.assertEqual(PotentialMatch.objects.count(), 3)
        self.assertEqual(
            set(PotentialMatch.objects.values_list("registered_student_id", flat=True)),
            {target.pk for target in self.targets},
        )

    def test_two_authors_can_target_the_same_student_independently(self):
        second_author = make_student(self.college, "A002", "Bob Author")
        shared_target = make_student(self.college, "T200", "Shared Target")
        first = make_entry(self.author, shared_target, priority=1)
        second = make_entry(second_author, shared_target, priority=1)

        match_entries_for(self.author)
        match_entries_for(second_author)

        proposals = PotentialMatch.objects.filter(registered_student=shared_target)
        self.assertEqual(proposals.count(), 2)
        self.assertEqual(
            set(proposals.values_list("crush_entry_id", flat=True)),
            {first.pk, second.pk},
        )
        self.assertEqual(pending_pairs(), [])

        reciprocal = make_entry(shared_target, self.author, priority=1)
        propose_for_entry(reciprocal)

        pairs = pending_pairs()
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["forward"].crush_entry_id, first.pk)
        self.assertEqual(
            PotentialMatch.objects.get(crush_entry=second).status,
            PotentialMatch.Status.PENDING,
        )

    def test_editing_one_slot_does_not_disturb_the_others(self):
        first = make_entry(self.author, self.targets[0], priority=1)
        second = make_entry(self.author, self.targets[1], priority=2)
        match_entries_for(self.author)
        old_proposal = PotentialMatch.objects.get(crush_entry=first)
        second_proposal = PotentialMatch.objects.get(crush_entry=second)

        repoint(first, self.targets[2])
        propose_for_entry(first)

        first.refresh_from_db()
        second.refresh_from_db()
        old_proposal.refresh_from_db()
        second_proposal.refresh_from_db()

        self.assertEqual(first.resolved_student_id, self.targets[2].pk)
        self.assertEqual(second.resolved_student_id, self.targets[1].pk)
        self.assertEqual(old_proposal.status, PotentialMatch.Status.STALE)
        self.assertEqual(second_proposal.status, PotentialMatch.Status.PENDING)
        self.assertTrue(
            PotentialMatch.objects.filter(
                crush_entry=first,
                registered_student=self.targets[2],
                status=PotentialMatch.Status.PENDING,
            ).exists()
        )

    def test_duplicate_roll_number_is_rejected_by_the_form(self):
        make_entry(self.author, self.targets[0], priority=1)
        payload = entry_payload(
            "crush2",
            self.targets[1],
            **{"crush2-roll_number": self.targets[0].roll_number},
        )
        form = CrushEntryForm(payload, author=self.author, priority=2, prefix="crush2")

        self.assertFalse(form.is_valid())
        self.assertIn("roll_number", form.errors)

    def test_own_roll_number_is_rejected_by_the_form(self):
        payload = entry_payload("crush1", self.author)
        form = CrushEntryForm(payload, author=self.author, priority=1, prefix="crush1")

        self.assertFalse(form.is_valid())
        self.assertIn("roll_number", form.errors)

    def test_priority_must_be_unique(self):
        make_entry(self.author, self.targets[0], priority=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_entry(self.author, self.targets[1], priority=1)

    def test_priority_must_stay_in_range(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_entry(self.author, self.targets[0], priority=4)

    def test_public_entry_payload_hides_priority(self):
        entry = make_entry(self.author, self.targets[0], priority=3)
        payload = entry.as_public_dict()
        self.assertEqual(set(payload), {"college", "masked_roll"})
        self.assertNotIn("priority", payload)


class DynamicScoringRegressionTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="Scoring College")
        self.author = make_student(self.college, "S001", "Alice Author")
        self.target = make_student(self.college, "S002", "Bob Target")
        self.entry = make_entry(self.author, self.target)

    def test_hard_conflict_makes_pair_ineligible(self):
        eligible = compare(self.entry, self.target)
        self.assertTrue(eligible.eligible)

        self.entry.course = "BBA"
        self.entry.save()
        verdict = compare(self.entry, self.target)

        self.assertFalse(verdict.eligible)
        self.assertTrue(any("course" in blocker for blocker in verdict.blockers))

    def test_editing_into_conflict_stales_and_revives_same_proposal(self):
        proposal = propose_for_entry(self.entry)[0]
        self.assertEqual(proposal.status, PotentialMatch.Status.PENDING)

        self.entry.course = "BBA"
        self.entry.save()
        propose_for_entry(self.entry)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, PotentialMatch.Status.STALE)

        self.entry.course = self.target.course
        self.entry.save()
        propose_for_entry(self.entry)
        proposal.refresh_from_db()

        self.assertEqual(proposal.status, PotentialMatch.Status.PENDING)
        self.assertEqual(proposal.invalidated_reason, "")
        self.assertEqual(proposal.scoring_version, MATCH_SCORING_VERSION)

    @override_settings(MATCH_MIN_CONFIDENCE=95.0)
    def test_confidence_floor_is_enforced(self):
        self.entry.full_name = "Zzz Qqq"
        self.entry.save()

        propose_for_entry(self.entry)

        self.assertFalse(PotentialMatch.objects.filter(crush_entry=self.entry).exists())

    def test_proposal_stamps_scoring_version_and_time(self):
        proposal = propose_for_entry(self.entry)[0]
        self.assertEqual(proposal.scoring_version, MATCH_SCORING_VERSION)
        self.assertIsNotNone(proposal.scored_at)

    def test_compare_does_not_touch_the_database(self):
        with self.assertNumQueries(0):
            compare(self.entry, self.target)


class ReciprocalMatchingRegressionTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="Mutual College")
        self.alice = make_student(self.college, "M001", "Alice Author")
        self.bob = make_student(self.college, "M002", "Bob Target")
        self.admin = make_admin()
        self.alice_entry = make_entry(self.alice, self.bob, priority=1)
        self.bob_entry = make_entry(self.bob, self.alice, priority=1)

    def _propose_both(self):
        propose_for_entry(self.alice_entry)
        propose_for_entry(self.bob_entry)

    def test_mutual_entries_create_pending_pair_without_match(self):
        self._propose_both()

        self.assertEqual(MutualMatch.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)
        pairs = pending_pairs()
        self.assertEqual(len(pairs), 1)

        self.alice_entry.refresh_from_db()
        self.bob_entry.refresh_from_db()
        self.assertEqual(self.alice_entry.resolved_student_id, self.bob.pk)
        self.assertEqual(self.bob_entry.resolved_student_id, self.alice.pk)

    def test_one_sided_entry_cannot_be_approved(self):
        propose_for_entry(self.alice_entry)
        proposal = PotentialMatch.objects.get(crush_entry=self.alice_entry)

        self.assertEqual(pending_pairs(), [])
        with self.assertRaises(ApprovalError):
            approve_potential_match(proposal, self.admin)

        self.assertEqual(MutualMatch.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_approval_creates_match_and_notifies_both_once(self):
        self._propose_both()
        proposal = PotentialMatch.objects.get(crush_entry=self.alice_entry)

        match = approve_potential_match(proposal, self.admin)

        self.assertEqual(match.status, MutualMatch.Status.MUTUAL)
        self.assertIsNotNone(match.notified_at)
        self.assertEqual(
            list(PotentialMatch.objects.filter(mutual_match=match).values_list(
                "status", flat=True
            )),
            [PotentialMatch.Status.APPROVED, PotentialMatch.Status.APPROVED],
        )
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(
            set(Notification.objects.values_list("student_id", flat=True)),
            {self.alice.pk, self.bob.pk},
        )
        for note in Notification.objects.all():
            self.assertNotIn("priority", note.message.lower())
            self.assertNotIn(self.alice.roll_number, note.message)
            self.assertNotIn(self.bob.roll_number, note.message)

    def test_second_approval_cannot_duplicate_notifications(self):
        self._propose_both()
        proposal = PotentialMatch.objects.get(crush_entry=self.alice_entry)
        approve_potential_match(proposal, self.admin)

        with self.assertRaises(ApprovalError):
            approve_potential_match(proposal, self.admin)

        self.assertEqual(MutualMatch.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 2)

    def test_block_prevents_approval(self):
        self._propose_both()
        proposal = PotentialMatch.objects.get(crush_entry=self.alice_entry)
        Block.objects.create(blocker=self.alice, blocked=self.bob)

        with self.assertRaises(ApprovalError):
            approve_potential_match(proposal, self.admin)
        self.assertEqual(MutualMatch.objects.count(), 0)

    def test_sealing_is_silent_and_idempotent(self):
        self.assertEqual(seal_secret(self.alice), 1)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(MutualMatch.objects.count(), 0)

        self.assertEqual(seal_secret(self.alice), 0)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(MutualMatch.objects.count(), 0)

    def test_removing_an_entry_retires_its_proposal(self):
        propose_for_entry(self.alice_entry)
        proposal = PotentialMatch.objects.get(crush_entry=self.alice_entry)

        self.alice_entry.is_active = False
        self.alice_entry.save(update_fields=["is_active"])
        retire_entry(self.alice_entry)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, PotentialMatch.Status.STALE)
        with self.assertRaises(ApprovalError):
            approve_potential_match(proposal, self.admin)

    def test_rejecting_a_pair_rejects_both_halves(self):
        self._propose_both()
        proposal = PotentialMatch.objects.get(crush_entry=self.alice_entry)

        reject_potential_match(proposal, self.admin, admin_notes="Not a match")

        self.assertEqual(
            PotentialMatch.objects.filter(
                status=PotentialMatch.Status.REJECTED
            ).count(),
            2,
        )
        self.assertEqual(MutualMatch.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_approval_delivers_email_after_commit(self):
        self._propose_both()
        proposal = PotentialMatch.objects.get(crush_entry=self.alice_entry)

        with mock.patch("campus.services.send_mail", return_value=True) as sender:
            with self.captureOnCommitCallbacks(execute=True):
                approve_potential_match(proposal, self.admin)

        self.assertEqual(sender.call_count, 2)
        self.assertEqual(
            set(
                Notification.objects.values_list("email_status", flat=True)
            ),
            {Notification.EmailStatus.SENT},
        )

    def test_approval_survives_email_failure(self):
        self._propose_both()
        proposal = PotentialMatch.objects.get(crush_entry=self.alice_entry)

        with mock.patch("campus.services.send_mail", return_value=False):
            with self.captureOnCommitCallbacks(execute=True):
                match = approve_potential_match(proposal, self.admin)

        self.assertEqual(match.status, MutualMatch.Status.MUTUAL)
        self.assertEqual(
            set(
                Notification.objects.values_list("email_status", flat=True)
            ),
            {Notification.EmailStatus.FAILED},
        )


class RegistrationEmailRegressionTests(TestCase):
    def _register(self):
        return self.client.post(
            reverse("accounts:register"),
            {
                "email": "newbie@example.edu",
                "password1": "a-very-strong-pass-1",
                "password2": "a-very-strong-pass-1",
                "agree": "on",
            },
        )

    def test_registration_queues_one_verification_email(self):
        response = self._register()

        self.assertRedirects(response, reverse("campus:campus_select"))
        user = User.objects.get(email="newbie@example.edu")
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(user.email_verification.email_status, "pending")
        self.assertIsNone(user.email_verification.sent_at)

        self.assertTrue(deliver_verification_email(user.email_verification.pk))
        self.assertEqual(len(mail.outbox), 1)
        user.email_verification.refresh_from_db()
        self.assertIsNotNone(user.email_verification.sent_at)
        self.assertFalse(user.email_verification.is_verified)

    def test_registration_never_claims_delivery_before_smtp_accepts(self):
        response = self._register()

        self.assertRedirects(response, reverse("campus:campus_select"))
        user = User.objects.get(email="newbie@example.edu")
        self.assertEqual(len(mail.outbox), 0)
        messages = [str(message) for message in response.wsgi_request._messages]
        self.assertFalse(any("emailed you a confirmation link" in message for message in messages))
        self.assertTrue(any("sending a confirmation link" in message for message in messages))

        with mock.patch(
            "config.mail._django_send_mail", side_effect=OSError("smtp down")
        ):
            with self.assertLogs("config.mail", level="ERROR"):
                self.assertFalse(deliver_verification_email(user.email_verification.pk))
        user.email_verification.refresh_from_db()
        self.assertEqual(user.email_verification.email_status, "failed")
        self.assertIsNone(user.email_verification.sent_at)

    def test_resend_is_throttled_by_cooldown(self):
        user = User.objects.create_user(
            username="student@example.edu",
            email="student@example.edu",
            password="pass-12345",
        )
        first = send_verification_email(user)
        second = send_verification_email(user)

        self.assertTrue(first.sent)
        self.assertEqual(second.reason, "already_queued")
        self.assertEqual(len(mail.outbox), 0)

        self.assertTrue(deliver_verification_email(user.email_verification.pk))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(send_verification_email(user).reason, "throttled")

    def test_failed_send_does_not_start_cooldown(self):
        user = User.objects.create_user(
            username="student@example.edu",
            email="student@example.edu",
            password="pass-12345",
        )
        send_verification_email(user)
        with mock.patch(
            "config.mail._django_send_mail", side_effect=OSError("smtp down")
        ):
            with self.assertLogs("config.mail", level="ERROR"):
                self.assertFalse(deliver_verification_email(user.email_verification.pk))

        user.email_verification.refresh_from_db()
        self.assertEqual(user.email_verification.email_status, "failed")
        self.assertIsNone(user.email_verification.sent_at)

        retried = send_verification_email(user)
        self.assertTrue(retried.sent)
        self.assertEqual(retried.reason, "queued")

    def test_new_student_joins_and_only_queues_proposals(self):
        college = College.objects.create(name="Joining College")
        author = make_student(college, "J001", "Alice Author")
        entry = CrushEntry.objects.create(
            submitted_by=author,
            priority=1,
            full_name="Bob Target",
            roll_number="J002",
            college=college,
            course="BCA",
            year=2,
            section="A",
        )

        joined = make_student(college, "J002", "Bob Target")
        match_new_student(joined)

        entry.refresh_from_db()
        self.assertEqual(entry.resolved_student_id, joined.pk)
        self.assertEqual(
            PotentialMatch.objects.filter(
                crush_entry=entry,
                registered_student=joined,
                status=PotentialMatch.Status.PENDING,
            ).count(),
            1,
        )
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(MutualMatch.objects.count(), 0)

    def test_registration_query_count_is_bounded(self):
        with CaptureQueriesContext(connection) as queries:
            response = self._register()

        self.assertEqual(response.status_code, 302)
        self.assertLess(len(queries), 80)


class PrivacyPermissionRegressionTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="Privacy College")
        self.alice = make_student(self.college, "P001", "Alice Author")
        self.bob = make_student(self.college, "P002", "Bob Target")
        self.alice_entry = make_entry(self.alice, self.bob, priority=1)
        self.bob_entry = make_entry(self.bob, self.alice, priority=1)

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(reverse("campus:secret"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_plain_student_cannot_open_any_staff_desk(self):
        self.client.force_login(self.alice.user)
        for name in ("staff_dashboard", "pending_matches", "identity_review"):
            response = self.client.get(reverse(f"campus:{name}"))
            self.assertRedirects(response, reverse("campus:dashboard"))

    def test_plain_staff_without_permissions_is_denied(self):
        staff = User.objects.create_user(
            username="staff@example.edu",
            email="staff@example.edu",
            password="pass-12345",
            is_staff=True,
        )
        self.client.force_login(staff)
        for name in ("pending_matches", "identity_review"):
            response = self.client.get(reverse(f"campus:{name}"))
            self.assertRedirects(
                response,
                reverse("campus:dashboard"),
                fetch_redirect_response=False,
            )

    def test_identity_reviewer_cannot_use_match_queue(self):
        staff = User.objects.create_user(
            username="identity@example.edu",
            email="identity@example.edu",
            password="pass-12345",
            is_staff=True,
        )
        staff.user_permissions.add(
            Permission.objects.get(codename="review_identitycandidate")
        )
        self.client.force_login(staff)

        self.assertEqual(
            self.client.get(reverse("campus:identity_review")).status_code, 200
        )
        self.assertRedirects(
            self.client.get(reverse("campus:pending_matches")),
            reverse("campus:dashboard"),
            fetch_redirect_response=False,
        )

    def test_match_reviewer_cannot_use_identity_desk(self):
        staff = User.objects.create_user(
            username="matches@example.edu",
            email="matches@example.edu",
            password="pass-12345",
            is_staff=True,
        )
        staff.user_permissions.add(
            Permission.objects.get(codename="verify_potentialmatch")
        )
        self.client.force_login(staff)

        self.assertEqual(
            self.client.get(reverse("campus:pending_matches")).status_code, 200
        )
        self.assertRedirects(
            self.client.get(reverse("campus:identity_review")),
            reverse("campus:dashboard"),
            fetch_redirect_response=False,
        )

    def test_student_cannot_edit_another_students_entry(self):
        self.client.force_login(self.alice.user)
        response = self.client.post(
            reverse("campus:edit_crush", args=[self.bob_entry.pk]),
            entry_payload("crush1", self.alice),
        )
        self.assertEqual(response.status_code, 404)

    def test_student_cannot_remove_another_students_entry(self):
        self.client.force_login(self.alice.user)
        response = self.client.post(
            reverse("campus:remove_crush", args=[self.bob_entry.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.bob_entry.refresh_from_db()
        self.assertTrue(self.bob_entry.is_active)

    def test_secret_desk_never_prints_priority(self):
        self.client.force_login(self.alice.user)
        html = self.client.get(reverse("campus:secret")).content.decode().lower()
        for leak in ("priority", "#1", "#2", "#3", "ranked"):
            self.assertNotIn(leak, html)

    def test_blocking_retires_entries_and_proposals(self):
        propose_for_entry(self.alice_entry)
        proposal = PotentialMatch.objects.get(crush_entry=self.alice_entry)
        self.client.force_login(self.alice.user)

        response = self.client.post(
            reverse("campus:block", args=[self.bob.pk]), {"confirm": "on"}
        )

        self.assertRedirects(response, reverse("campus:matches"))
        self.alice_entry.refresh_from_db()
        proposal.refresh_from_db()
        self.assertFalse(self.alice_entry.is_active)
        self.assertEqual(proposal.status, PotentialMatch.Status.STALE)
        self.assertTrue(
            Block.objects.filter(blocker=self.alice, blocked=self.bob).exists()
        )

    def test_delete_crushes_only_affects_the_caller(self):
        self.client.force_login(self.bob.user)
        response = self.client.post(reverse("campus:delete_crushes"))

        self.assertEqual(response.status_code, 302)
        self.alice_entry.refresh_from_db()
        self.bob_entry.refresh_from_db()
        self.assertTrue(self.alice_entry.is_active)
        self.assertFalse(self.bob_entry.is_active)

    def test_report_stores_reporter_privately(self):
        self.client.force_login(self.alice.user)
        response = self.client.post(
            reverse("campus:report", args=[self.bob.pk]),
            {"reason": Report.Reason.WRONG_STUDENT},
        )

        self.assertEqual(response.status_code, 302)
        report = Report.objects.get(reported=self.bob)
        self.assertEqual(report.reporter_id, self.alice.pk)
        self.assertEqual(self.bob.notifications.count(), 0)


class DatabaseIntegrityRegressionTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="Integrity College")
        self.a = make_student(self.college, "I001", "Alice Author")
        self.b = make_student(self.college, "I002", "Bob Target")
        self.c = make_student(self.college, "I003", "Cara Third")

    def test_student_roll_is_unique_per_college(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_student(self.college, "I001", "Duplicate Roll")

    def test_same_roll_is_allowed_on_another_college(self):
        other = College.objects.create(name="Second Integrity College")
        duplicate = make_student(other, "I001", "Duplicate Roll")
        self.assertNotEqual(duplicate.college_id, self.college.pk)

    def test_entry_priority_is_unique_per_author(self):
        make_entry(self.a, self.b, priority=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_entry(self.a, self.c, priority=1)

    def test_database_rejects_duplicate_active_target_with_same_roll(self):
        make_entry(self.a, self.b, priority=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_entry(self.a, self.b, priority=2)

    def test_duplicate_target_is_allowed_after_soft_delete(self):
        first = make_entry(self.a, self.b, priority=1)
        first.is_active = False
        first.save(update_fields=["is_active"])

        replacement = make_entry(self.a, self.b, priority=2)
        self.assertEqual(replacement.normalized_roll_number, self.b.normalized_roll_number)

    def test_blank_roll_entries_are_not_constrained_as_duplicates(self):
        make_entry(self.a, self.b, priority=1, roll_number="")
        second = make_entry(self.a, self.b, priority=2, roll_number="")
        self.assertEqual(second.normalized_roll_number, "")

    def test_entry_priority_is_bounded(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_entry(self.a, self.b, priority=4)

    def test_resolved_link_requires_resolved_status(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CrushEntry.objects.create(
                    submitted_by=self.a,
                    priority=2,
                    full_name=self.b.full_name,
                    roll_number=self.b.roll_number,
                    college=self.college,
                    course=self.b.course,
                    year=self.b.year,
                    section=self.b.section,
                    resolved_student=self.b,
                )

    def test_potential_match_pair_is_unique(self):
        entry = make_entry(self.a, self.b, priority=1)
        PotentialMatch.objects.create(crush_entry=entry, registered_student=self.b)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PotentialMatch.objects.create(
                    crush_entry=entry, registered_student=self.b
                )

    def test_identity_candidate_pair_is_unique(self):
        entry = make_entry(self.a, self.b, priority=1)
        IdentityCandidate.objects.create(crush_entry=entry, candidate=self.b)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                IdentityCandidate.objects.create(crush_entry=entry, candidate=self.b)

    def test_mutual_match_orders_pair_and_rejects_duplicates(self):
        match = MutualMatch.objects.create(user_a=self.b, user_b=self.a)
        self.assertLess(match.user_a_id, match.user_b_id)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MutualMatch.objects.create(user_a=self.a, user_b=self.b)

    def test_identity_audit_is_append_only(self):
        entry = make_entry(self.a, self.b, priority=1)
        resolve_entry(entry)
        before = IdentityResolutionAudit.objects.count()
        resolve_entry(entry)
        self.assertEqual(IdentityResolutionAudit.objects.count(), before)


class ScaleAndQueryRegressionTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="Scale College")
        self.author = make_student(self.college, "Q001", "Alice Author")
        self.target = make_student(self.college, "Q002", "Bob Target")
        self.entry = make_entry(self.author, self.target)

    def test_candidate_scan_is_college_scoped(self):
        other = College.objects.create(name="Noise College")
        for index in range(40):
            make_student(other, f"N{index:03d}", f"Bob Noise {index}")

        candidates = generate_candidates(self.entry)

        self.assertTrue(candidates)
        self.assertEqual(
            {candidate.student.college_id for candidate in candidates},
            {self.college.pk},
        )

    def test_candidate_scan_query_count_is_bounded(self):
        with CaptureQueriesContext(connection) as queries:
            generate_candidates(self.entry)
        self.assertLessEqual(len(queries), 8)

    def test_pending_pairs_query_count_is_constant(self):
        for index in range(4):
            left = make_student(self.college, f"Q1{index}", f"Left {index}")
            right = make_student(self.college, f"Q2{index}", f"Right {index}")
            entry_left = make_entry(left, right, priority=1)
            entry_right = make_entry(right, left, priority=1)
            propose_for_entry(entry_left)
            propose_for_entry(entry_right)

        with CaptureQueriesContext(connection) as queries:
            pairs = pending_pairs()
        self.assertEqual(len(pairs), 4)
        self.assertLessEqual(len(queries), 2)


class ManagementCommandRegressionTests(TestCase):
    def setUp(self):
        self.college = College.objects.create(name="Command College")
        self.author = make_student(self.college, "C001", "Alice Author")
        self.target = make_student(self.college, "C002", "Bob Target")

    def test_reevaluate_matching_resolves_and_proposes(self):
        entry = make_entry(self.author, self.target)
        out = StringIO()

        call_command("reevaluate_matching", stdout=out)

        entry.refresh_from_db()
        self.assertEqual(entry.resolved_student_id, self.target.pk)
        self.assertTrue(
            PotentialMatch.objects.filter(
                crush_entry=entry, registered_student=self.target
            ).exists()
        )
        self.assertIn("Re-evaluated", out.getvalue())

    def test_audit_matching_reports_health(self):
        make_entry(self.author, self.target)
        out = StringIO()

        call_command("audit_matching", stdout=out)

        output = out.getvalue()
        self.assertIn("Active crush entries", output)
        self.assertIn("Notification email outbox", output)

    def test_retry_notifications_sends_failed_mail(self):
        notification = Notification.objects.create(
            student=self.author,
            kind=Notification.Kind.MUTUAL,
            message="Someone you secretly selected also selected you.",
            dedupe_key="regression-retry-1",
            email_status=Notification.EmailStatus.FAILED,
        )

        with mock.patch("campus.services.send_mail", return_value=True):
            call_command("retry_notifications", stdout=StringIO())

        notification.refresh_from_db()
        self.assertEqual(notification.email_status, Notification.EmailStatus.SENT)
        self.assertEqual(notification.email_attempts, 1)
        self.assertIsNotNone(notification.email_sent_at)
