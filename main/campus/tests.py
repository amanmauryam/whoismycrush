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

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from .forms import CrushEntryForm, StudentIdentityForm
from .matching import MIN_CONFIDENCE, compare, pending_pairs
from .models import (
    MAX_CRUSHES,
    College,
    CrushEntry,
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
        before = proposal.confidence_score

        self.client.force_login(self.a.user)
        self.client.post(
            reverse("campus:edit_crush", args=[entry.pk]),
            entry_payload("crush1", self.b, **{"crush1-full_name": "Priyaa"}),
        )
        proposal.refresh_from_db()
        self.assertLess(proposal.confidence_score, before)

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
        self.assertFalse(
            PotentialMatch.objects.filter(
                crush_entry=entry, registered_student=self.b
            ).exists()
        )
        self.assertTrue(
            PotentialMatch.objects.filter(
                crush_entry=entry, registered_student=self.c
            ).exists()
        )

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
        approve_potential_match(self.proposal, self.admin)
        with self.assertRaises(ApprovalError):
            approve_potential_match(self.proposal, self.admin)
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
            reverse("campus:pending_matches"),
            reverse("campus:pending_match_detail", args=[self.proposal.pk]),
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
