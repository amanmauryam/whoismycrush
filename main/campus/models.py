from __future__ import annotations

import datetime as dt
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

MAX_CRUSHES = 3

_NON_ALNUM = re.compile(r"[^A-Z0-9]+")
_NON_ALPHA = re.compile(r"[^A-Z0-9 ]+")
_SPACES = re.compile(r"\s+")

# Titles/honorifics a student may or may not type. Dropped before comparing so
# "Sharma, Priya" and "Priya Sharma" are treated as one person.
_NAME_NOISE = {
    "mr", "mrs", "ms", "miss", "dr", "prof", "professor", "sri", "smt", "kum",
    "kumari", "shri", "smt", "bhai", "didi", "sir", "madam", "ji",
}

#: 1..5 with readable labels, shared by ``StudentProfile`` and ``CrushEntry`` so
#: the two structures stay directly comparable (requirements 3/7).
YEAR_CHOICES = [
    (n, f"{n}{'st' if n == 1 else 'nd' if n == 2 else 'rd' if n == 3 else 'th'} Year")
    for n in range(1, 6)
]


def normalize_roll_number(value: str) -> str:
    """Canonical identity key for a roll number inside a college.

    ``"23bca-104 "`` -> ``"23BCA104"``. Case, spacing and punctuation never
    matter, which is what lets a student type their roll the way it is
    printed on their ID card and still resolve to the same person.

    Only case and separators are removed -- never characters, because
    collapsing ``BCA-027`` and ``BCA27`` together could fuse two real
    students (requirements 20).
    """
    return _NON_ALNUM.sub("", (value or "").upper())


def normalize_name(value: str) -> str:
    """Canonical comparison form for a person's name (requirements 7).

    Uppercases, strips punctuation, drops honorifics, collapses whitespace and
    sorts nothing. ``"  Riya  Sharma "``, ``"riya sharma"`` and
    ``"Sharma, Riya."`` all normalize to the same token bag, while ``"Riya S."``
    keeps its middle initial so it never silently equals ``"Riya Sharma"``.
    """
    raw = _NON_ALPHA.sub(" ", (value or "").upper())
    tokens = [t for t in _SPACES.split(raw) if t and t not in _NAME_NOISE]
    return " ".join(tokens)


def name_tokens(value: str) -> set[str]:
    return set(normalize_name(value).split())


def normalize_text(value: str) -> str:
    """Case/space/punctuation-normalized form for course, section, dept, etc."""
    return _SPACES.sub(" ", _NON_ALPHA.sub(" ", (value or "").upper())).strip()


class College(models.Model):
    """A campus / community. Crushes never cross this boundary."""

    name = models.CharField(max_length=180, unique=True)
    normalized_name = models.CharField(
        max_length=180,
        blank=True,
        db_index=True,
        help_text="Case/punctuation-insensitive form used to spot duplicate campuses.",
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        blank=True,
        help_text="Public URL fragment, derived from the name.",
    )
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=120, blank=True)
    domain = models.CharField(
        max_length=180,
        blank=True,
        help_text="Optional email domain used to hint campus membership.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["normalized_name"]),
            models.Index(fields=["city"]),
        ]

    def __str__(self) -> str:
        return self.display_name

    def save(self, *args, **kwargs):
        self.normalized_name = normalize_text(self.name)
        if not self.slug:
            self.slug = self._unique_slug()
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = {
                *kwargs["update_fields"],
                "normalized_name",
                "slug",
            }
        super().save(*args, **kwargs)

    def _unique_slug(self) -> str:
        base = slugify(self.name)[:180] or "campus"
        candidate = base
        suffix = 2
        while College.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def get_absolute_url(self) -> str:
        return reverse("campus:college_landing", kwargs={"slug": self.slug})

    @property
    def join_path(self) -> str:
        return reverse("campus:join", kwargs={"slug": self.slug})

    @property
    def display_name(self) -> str:
        if self.city and self.state:
            return f"{self.name}, {self.city}"
        return self.name

    def student_count(self) -> int:
        return self.student_profiles.count()


class StudentProfile(models.Model):
    """The private campus identity a student builds after signing up.

    This row is the *only* thing that identifies a person. Crushes are typed
    in by hand as ``CrushEntry`` rows, so a crush never has to have an account
    and nobody is ever looked up or selected from a directory
    (design.md 17/18/36, requirements 1/4).
    """

    class Gender(models.TextChoices):
        FEMALE = "female", "Female"
        MALE = "male", "Male"
        NON_BINARY = "non_binary", "Non-binary"
        UNDISCLOSED = "undisclosed", "Prefer not to say"

    class Course(models.TextChoices):
        BCA = "BCA", "BCA"
        BBA = "BBA", "BBA"
        BCOM = "BCOM", "B.Com"
        BA = "BA", "BA"
        BSC = "BSC", "B.Sc"
        BTECH = "BTECH", "B.Tech"
        MCA = "MCA", "MCA"
        MA = "MA", "MA"
        MBA = "MBA", "MBA"
        BED = "BED", "B.Ed"
        OTHER = "OTHER", "Other"

    class Section(models.TextChoices):
        A = "A", "A"
        B = "B", "B"
        C = "C", "C"
        D = "D", "D"
        NONE = "", "Not applicable"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student")
    college = models.ForeignKey(
        College, on_delete=models.PROTECT, related_name="student_profiles"
    )
    full_name = models.CharField(max_length=120)
    normalized_name = models.CharField(max_length=120, blank=True, db_index=True)
    nickname = models.CharField(max_length=60, blank=True)
    roll_number = models.CharField(max_length=60)
    normalized_roll_number = models.CharField(max_length=60, db_index=True)
    course = models.CharField(max_length=20, choices=Course.choices)
    year = models.PositiveSmallIntegerField(choices=YEAR_CHOICES)
    section = models.CharField(max_length=4, choices=Section.choices, blank=True)
    gender = models.CharField(
        max_length=20, choices=Gender.choices, default=Gender.UNDISCLOSED
    )
    date_of_birth = models.DateField(null=True, blank=True)
    department = models.CharField(
        max_length=120,
        blank=True,
        help_text="Optional. Extra corroboration when verifying a match.",
    )
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["college", "normalized_roll_number"],
                name="unique_student_per_college_roll",
            ),
            models.CheckConstraint(
                condition=Q(year__gte=1) & Q(year__lte=5), name="student_year_range"
            ),
        ]
        indexes = [
            models.Index(fields=["college", "normalized_roll_number"]),
            models.Index(fields=["college", "normalized_name"]),
            models.Index(fields=["college", "full_name"]),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} · {self.college.name}"

    def save(self, *args, **kwargs):
        self.normalized_roll_number = normalize_roll_number(self.roll_number)
        self.normalized_name = normalize_name(self.full_name)
        if not self.normalized_roll_number:
            raise ValidationError({"roll_number": "Enter your roll number."})
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = {
                *kwargs["update_fields"],
                "normalized_name",
                "normalized_roll_number",
            }
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        clash = (
            StudentProfile.objects.filter(
                college_id=self.college_id,
                normalized_roll_number=self.normalized_roll_number,
            )
            .exclude(pk=self.pk)
            .exists()
        )
        if clash:
            raise ValidationError(
                {"roll_number": "That roll number already exists at this campus."}
            )

    # -- display helpers -------------------------------------------------
    @property
    def masked_roll_number(self) -> str:
        """Never render a full roll number (design.md 15/16/32)."""
        roll = self.roll_number
        if len(roll) <= 3:
            return "•••"
        return "•••" + roll[-3:]

    @property
    def display_name(self) -> str:
        return self.nickname or self.full_name

    @property
    def course_line(self) -> str:
        year = self.get_year_display()
        base = f"{self.get_course_display()} · {year}"
        if self.section:
            base += f" · Section {self.section}"
        return base

    @property
    def age(self) -> int | None:
        if not self.date_of_birth:
            return None
        today = timezone.localdate()
        return (
            today.year
            - self.date_of_birth.year
            - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        )

    def is_adult(self, minimum: int = 18) -> bool:
        age = self.age
        return age is None or age >= minimum


class CrushEntryQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def for_student(self, student: StudentProfile):
        """Only ever the caller's own rows. There is no unscoped accessor."""
        return self.active().filter(submitted_by=student).select_related("college")


class CrushEntry(models.Model):
    """A hand-typed "I secretly like this person" record (requirements 1-5).

    The submitted details are kept independently of a registered account. A
    crush usually has no account, so this row never *requires* a
    ``StudentProfile``. ``resolved_student`` is filled only after the identity
    engine finds sufficient, reviewed evidence; it is a link, not a guess.

    ``priority`` is an internal 1..3 ordering. It exists only so the admin can
    sanity-check a submission during verification. It must never be rendered,
    emailed, or exposed to either student (requirements 2/13).
    """

    class ResolutionStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        CANDIDATE_FOUND = "candidate_found", "Candidate found"
        NEEDS_REVIEW = "needs_review", "Needs review"
        RESOLVED = "resolved", "Resolved"
        UNRESOLVABLE = "unresolvable", "Unresolvable"

    submitted_by = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="crush_entries"
    )
    priority = models.PositiveSmallIntegerField(
        help_text="Internal ordering 1-3. Never shown to either student."
    )
    full_name = models.CharField(max_length=255)
    normalized_name = models.CharField(max_length=255, blank=True, db_index=True)
    roll_number = models.CharField(max_length=100, blank=True)
    normalized_roll_number = models.CharField(
        max_length=100, blank=True, db_index=True
    )
    college = models.ForeignKey(
        College, on_delete=models.PROTECT, related_name="crush_entries"
    )
    course = models.CharField(max_length=20, choices=StudentProfile.Course.choices)
    year = models.PositiveSmallIntegerField(choices=YEAR_CHOICES)
    section = models.CharField(max_length=50, blank=True)
    department = models.CharField(max_length=120, blank=True)
    nickname = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    # -- identity resolution state (independent of match status) -----------
    identity_status = models.CharField(
        max_length=20,
        choices=ResolutionStatus.choices,
        default=ResolutionStatus.PENDING,
        db_index=True,
    )
    resolved_student = models.ForeignKey(
        StudentProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_crush_entries",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Advisory identity confidence. Never shown to students.",
    )
    resolution_method = models.CharField(max_length=40, blank=True)
    resolution_notes = models.CharField(max_length=300, blank=True)
    resolution_scoring_version = models.CharField(max_length=40, blank=True)
    resolution_scored_at = models.DateTimeField(null=True, blank=True)
    original_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "First submitted values, preserved for audit even after the student "
            "corrects the entry. Never shown to either student."
        ),
    )

    objects = CrushEntryQuerySet.as_manager()

    class Meta:
        ordering = ["priority", "created_at"]
        constraints = [
            # One entry per slot, so a priority can never be ambiguous.
            models.UniqueConstraint(
                fields=["submitted_by", "priority"], name="unique_entry_per_priority"
            ),
            models.CheckConstraint(
                condition=Q(priority__gte=1) & Q(priority__lte=MAX_CRUSHES),
                name="crush_entry_priority_range",
            ),
            # The form checks this sequentially, but two concurrent submissions
            # can both pass validation. The database must be the final guard so
            # one person is never stored twice in the same active list.
            models.UniqueConstraint(
                fields=["submitted_by", "normalized_roll_number"],
                condition=Q(is_active=True) & ~Q(normalized_roll_number=""),
                name="unique_active_entry_target_roll",
            ),
            # A resolved link may only exist on a resolved row. The reverse is
            # enforced by the service, because account deletion sets the link
            # to NULL while the cleanup signal moves the row back to pending.
            models.CheckConstraint(
                condition=Q(resolved_student__isnull=True)
                | Q(identity_status="resolved"),
                name="crush_resolved_link_requires_status",
            ),
        ]
        indexes = [
            # Exact roll lookup and name-first fallback are the two indexed
            # candidate paths. Expensive fuzzy comparison happens after the
            # college scope has already narrowed the rows.
            models.Index(fields=["college", "normalized_roll_number"]),
            models.Index(fields=["college", "normalized_name"]),
            models.Index(fields=["identity_status", "is_active"]),
            models.Index(fields=["submitted_by", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"#{self.priority} · {self.full_name}"

    def save(self, *args, **kwargs):
        self.normalized_name = normalize_name(self.full_name)
        self.normalized_roll_number = normalize_roll_number(self.roll_number)
        if self._state.adding and not self.original_payload:
            self.original_payload = {
                "full_name": self.full_name,
                "roll_number": self.roll_number,
                "college_id": self.college_id,
                "course": self.course,
                "year": self.year,
                "section": self.section,
                "department": self.department,
                "nickname": self.nickname,
            }
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = {
                *kwargs["update_fields"],
                "normalized_name",
                "normalized_roll_number",
            }
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.priority and not 1 <= self.priority <= MAX_CRUSHES:
            raise ValidationError({"priority": "Choose between 1 and 3."})
        normalized_roll = normalize_roll_number(self.roll_number)
        if (
            self.submitted_by_id
            and self.is_active
            and normalized_roll
            and CrushEntry.objects.filter(
                submitted_by_id=self.submitted_by_id,
                is_active=True,
                normalized_roll_number=normalized_roll,
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError(
                {
                    "roll_number": (
                        "You already entered someone with this campus and roll "
                        "number."
                    )
                }
            )
        if (
            self.submitted_by_id
            and self.college_id
            and self.submitted_by.college_id != self.college_id
        ):
            raise ValidationError(
                {"college": "A crush must be on the student's own campus."}
            )
        if (
            self.submitted_by_id
            and self.resolved_student_id
            and self.submitted_by_id == self.resolved_student_id
        ):
            raise ValidationError("You cannot enter yourself as a crush.")
        if self.resolved_student_id and self.resolved_student_id != self.submitted_by_id:
            if self.college_id and self.resolved_student and (
                self.college_id != self.resolved_student.college_id
            ):
                raise ValidationError("A resolved crush must be on the same campus.")

    @property
    def masked_roll_number(self) -> str:
        roll = self.roll_number
        if not roll:
            return "—"
        if len(roll) <= 3:
            return "•••"
        return "•••" + roll[-3:]

    @property
    def has_roll_number(self) -> bool:
        return bool(self.normalized_roll_number)

    @property
    def course_line(self) -> str:
        base = f"{self.get_course_display()} · {self.get_year_display()}"
        if self.section:
            base += f" · Section {self.section}"
        return base

    def as_public_dict(self) -> dict:
        """Privacy-safe payload. Deliberately excludes priority."""
        return {"college": self.college_id, "masked_roll": self.masked_roll_number}


class MutualMatchQuerySet(models.QuerySet):
    def for_student(self, student: StudentProfile):
        return self.filter(Q(user_a=student) | Q(user_b=student))

    def open(self):
        return self.exclude(status=MutualMatch.Status.CLOSED)

    def with_counterpart(self, student: StudentProfile):
        return self.select_related("user_a", "user_b")


class MutualMatch(models.Model):
    """A confirmed reciprocal selection. Never exposes who picked first."""

    class Status(models.TextChoices):
        MUTUAL = "mutual", "Mutual"
        REVEAL_PENDING = "reveal_pending", "Reveal pending"
        REVEALED = "revealed", "Revealed"
        CLOSED = "closed", "Closed"

    # user_a is always the lower primary key, which keeps (user_a, user_b) unique.
    user_a = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="matches_as_a"
    )
    user_b = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="matches_as_b"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.MUTUAL
    )
    user_a_consented = models.BooleanField(default=False)
    user_b_consented = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    revealed_at = models.DateTimeField(null=True, blank=True)
    notified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set atomically before notifications, so a pair is announced at most once.",
    )

    objects = MutualMatchQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user_a", "user_b"], name="unique_match_pair"),
            models.CheckConstraint(condition=Q(user_a__lt=F("user_b")), name="match_ordered_pair"),
        ]
        indexes = [
            models.Index(fields=["user_a", "status"]),
            models.Index(fields=["user_b", "status"]),
        ]

    def __str__(self) -> str:
        return f"Mutual match #{self.pk}"

    def other(self, student: StudentProfile) -> StudentProfile:
        return self.user_b if self.user_a_id == student.pk else self.user_a

    def has_consented(self, student: StudentProfile) -> bool:
        return self.user_a_consented if self.user_a_id == student.pk else self.user_b_consented

    def record_consent(self, student: StudentProfile) -> None:
        if self.user_a_id == student.pk:
            self.user_a_consented = True
        else:
            self.user_b_consented = True

    def save(self, *args, **kwargs):
        if self.user_a_id and self.user_b_id and self.user_a_id > self.user_b_id:
            self.user_a, self.user_b = self.user_b, self.user_a
            self.user_a_consented, self.user_b_consented = (
                self.user_b_consented,
                self.user_a_consented,
            )
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = {
                    *kwargs["update_fields"],
                    "user_a",
                    "user_b",
                    "user_a_consented",
                    "user_b_consented",
                }
        super().save(*args, **kwargs)

    def sync_status(self, *, save: bool = True) -> None:
        both = self.user_a_consented and self.user_b_consented
        if both and self.status != self.Status.CLOSED:
            self.status = self.Status.REVEALED
            if self.revealed_at is None:
                self.revealed_at = timezone.now()
        elif self.user_a_consented or self.user_b_consented:
            if self.status not in {self.Status.CLOSED, self.Status.REVEALED}:
                self.status = self.Status.REVEAL_PENDING
        elif self.status not in {self.Status.CLOSED, self.Status.REVEALED}:
            self.status = self.Status.MUTUAL
        if save:
            self.save(update_fields=["status", "revealed_at"])

    def get_absolute_url(self) -> str:
        return reverse("campus:match_detail", args=[self.pk])

    # Public (privacy-safe) payload. Deliberately excludes priority.
    def as_public_dict(self) -> dict:
        return {"match": True, "status": self.status}


class PotentialMatchQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(status=PotentialMatch.Status.PENDING)

    def stale(self):
        return self.filter(status=PotentialMatch.Status.STALE)

    def approved(self):
        return self.filter(status=PotentialMatch.Status.APPROVED)

    def for_review(self):
        return self.select_related(
            "crush_entry",
            "crush_entry__college",
            "crush_entry__submitted_by",
            "crush_entry__submitted_by__college",
            "registered_student",
            "registered_student__college",
            "verified_by",
        )


class PotentialMatch(models.Model):
    """"A submitted CrushEntry looks like a real registered student."

    This is a *proposal*, never a result. Nothing is ever shown to either
    student at this stage -- not even a hint that they were entered (requirement
    17). Only an admin can turn one into a real ``MutualMatch``
    (requirements 9/10/26).

    The row is deliberately single-direction (``entry`` describes
    ``registered_student``). A genuine mutual crush is the *pair* of reciprocal
    rows; :attr:`reciprocal` finds the other half.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Verification"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        STALE = "stale", "Stale / No longer eligible"

    crush_entry = models.ForeignKey(
        CrushEntry, on_delete=models.CASCADE, related_name="potential_matches"
    )
    registered_student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="potential_matches"
    )
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Advisory score for the reviewing admin. Never shown to students.",
    )
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    #: Why the matcher proposed this, e.g. "roll+course+year+section agree".
    match_reasons = models.CharField(max_length=300, blank=True)
    invalidated_reason = models.CharField(max_length=300, blank=True)
    scoring_version = models.CharField(max_length=40, blank=True, default="legacy")
    scored_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_matches",
    )
    #: Set once an approved ``MutualMatch`` was produced from this proposal.
    mutual_match = models.ForeignKey(
        MutualMatch,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_matches",
    )

    objects = PotentialMatchQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["crush_entry", "registered_student"],
                name="unique_potential_match",
            )
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["registered_student", "status"]),
            models.Index(fields=["crush_entry", "status"]),
        ]
        permissions = [
            ("verify_potentialmatch", "Can approve or reject potential matches"),
        ]

    def __str__(self) -> str:
        return f"PM#{self.pk} · {self.crush_entry_id} → {self.registered_student_id}"

    @property
    def author(self) -> StudentProfile:
        """The student who typed this entry -- "Person A" on the admin page."""
        return self.crush_entry.submitted_by

    @property
    def candidate(self) -> StudentProfile:
        """The registered student it points at -- "Person B"."""
        return self.registered_student

    @property
    def is_resolved(self) -> bool:
        return self.status in {self.Status.APPROVED, self.Status.REJECTED}

    @property
    def is_stale(self) -> bool:
        return self.status == self.Status.STALE

    @property
    def confidence_percent(self) -> str:
        if self.confidence_score is None:
            return "—"
        return f"{self.confidence_score:.0f}%"

    @property
    def reciprocal(self) -> "PotentialMatch | None":
        """The mirror row, if the candidate also entered this author."""
        return (
            PotentialMatch.objects.filter(
                crush_entry__submitted_by=self.registered_student,
                registered_student=self.author,
            )
            .exclude(pk=self.pk)
            .order_by("pk")
            .first()
        )

    @property
    def is_reciprocal(self) -> bool:
        return self.reciprocal is not None

    @property
    def pair_key(self) -> tuple[int, int]:
        """Order-independent key identifying the two students."""
        return tuple(sorted([self.author.pk, self.registered_student.pk]))


class IdentityCandidate(models.Model):
    """One possible registered identity for a hand-typed crush entry.

    This is deliberately separate from ``PotentialMatch``: identity resolution
    answers *who is this person?*, while a potential match answers *do two
    people like each other?*. A candidate never notifies anyone and never
    appears in a student-facing view.
    """

    class Status(models.TextChoices):
        CANDIDATE = "candidate", "Candidate"
        NEEDS_REVIEW = "needs_review", "Needs review"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        DEFERRED = "deferred", "Deferred"
        SUPERSEDED = "superseded", "Superseded"

    crush_entry = models.ForeignKey(
        CrushEntry, on_delete=models.CASCADE, related_name="identity_candidates"
    )
    candidate = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="identity_candidates",
    )
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Advisory identity score for reviewers. Never shown to students.",
    )
    name_similarity = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True
    )
    evidence = models.JSONField(
        default=dict,
        blank=True,
        help_text="Explainable scoring inputs: roll, name, course, year, conflicts.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CANDIDATE, db_index=True
    )
    scoring_version = models.CharField(max_length=40, blank=True, default="legacy")
    scored_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_identity_candidates",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-confidence_score", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["crush_entry", "candidate"],
                name="unique_identity_candidate",
            )
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["candidate", "status"]),
            models.Index(fields=["crush_entry", "status"]),
        ]
        permissions = [
            (
                "review_identitycandidate",
                "Can review and confirm ambiguous crush identities",
            ),
        ]

    def __str__(self) -> str:
        return f"IC#{self.pk} · entry {self.crush_entry_id} → {self.candidate_id}"

    @property
    def is_open(self) -> bool:
        return self.status in {
            self.Status.CANDIDATE,
            self.Status.NEEDS_REVIEW,
            self.Status.DEFERRED,
        }

    @property
    def author(self) -> StudentProfile:
        return self.crush_entry.submitted_by


class IdentityResolutionAudit(models.Model):
    """Append-only record of identity decisions.

    Only ids and a short reason are stored. The original crush details stay on
    ``CrushEntry``; this table exists to answer *who decided what, when* without
    duplicating sensitive text into logs or exports.
    """

    class Action(models.TextChoices):
        AUTO_RESOLVED = "auto_resolved", "Auto resolved"
        CONFIRMED = "confirmed", "Confirmed by reviewer"
        REJECTED = "rejected", "Rejected by reviewer"
        DEFERRED = "deferred", "Deferred by reviewer"
        INVALIDATED = "invalidated", "Invalidated"
        UNRESOLVABLE = "unresolvable", "Marked unresolvable"
        REOPENED = "reopened", "Reopened"

    crush_entry = models.ForeignKey(
        CrushEntry,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolution_audit",
    )
    candidate = models.ForeignKey(
        StudentProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolution_audit",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="identity_resolution_actions",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    candidate_from_status = models.CharField(max_length=30, blank=True)
    candidate_to_status = models.CharField(max_length=30, blank=True)
    notes = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["crush_entry", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} · entry {self.crush_entry_id}"


class Rose(models.Model):
    """Optional post-match gift. Never a payment for basic matching."""

    class Type(models.TextChoices):
        RED = "red", "Red Rose"
        SILVER = "silver", "Silver Rose"
        GOLDEN = "golden", "Golden Rose"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    CATALOG = {
        Type.RED: 100,
        Type.SILVER: 250,
        Type.GOLDEN: 500,
    }

    match = models.ForeignKey(MutualMatch, on_delete=models.CASCADE, related_name="roses")
    sender = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="roses_sent"
    )
    receiver = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="roses_received"
    )
    rose_type = models.CharField(max_length=10, choices=Type.choices)
    amount = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=180, blank=True)
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_rose_type_display()} rose · {self.amount}"


class Block(models.Model):
    blocker = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="blocks_made"
    )
    blocked = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="blocks_received"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_block_pair")
        ]

    def __str__(self) -> str:
        return f"{self.blocker_id} blocked {self.blocked_id}"


class Report(models.Model):
    """Anti-abuse: report another student. Never reveals reporter identity."""

    class Reason(models.TextChoices):
        WRONG_STUDENT = "wrong_student", "This is not the person I meant"
        FAKE_PROFILE = "fake_profile", "Fake or impersonating profile"
        HARASSMENT = "harassment", "Harassment or bullying"
        INAPPROPRIATE = "inappropriate", "Inappropriate content or message"
        DUPLICATE = "duplicate", "Duplicate campus identity"
        OTHER = "other", "Something else"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWED = "reviewed", "Reviewed"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(
        StudentProfile, on_delete=models.SET_NULL, null=True, related_name="reports_filed"
    )
    reported = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="reports_against"
    )
    reason = models.CharField(max_length=30, choices=Reason.choices)
    detail = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self) -> str:
        return f"{self.get_reason_display()} · {self.status}"


class CollegeInvite(models.Model):
    """'Can't find them? Invite your college.' (design.md 19/46)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    college = models.ForeignKey(
        College, on_delete=models.CASCADE, related_name="invites"
    )
    created_by = models.ForeignKey(
        StudentProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invites_sent",
    )
    email = models.EmailField(blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Invite for {self.college_id} ({self.status})"


class Notification(models.Model):
    """Private, deliberately vague notifications (design.md 47/48)."""

    class Kind(models.TextChoices):
        MUTUAL = "mutual", "Mutual crush"
        REVEAL = "reveal", "Reveal"
        ROSE = "rose", "Rose"
        SYSTEM = "system", "System"

    class EmailStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.SYSTEM)
    message = models.CharField(max_length=200)
    url = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    #: Stable key makes repeated events (approval retries, two reveal clicks)
    #: idempotent instead of creating duplicate notifications.
    dedupe_key = models.CharField(max_length=160, null=True, blank=True, unique=True)
    email_status = models.CharField(
        max_length=12,
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING,
        db_index=True,
    )
    email_attempts = models.PositiveSmallIntegerField(default=0)
    email_last_error = models.CharField(max_length=300, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_last_attempt_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "is_read"]),
            models.Index(fields=["email_status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return self.message


@receiver(pre_delete, sender=StudentProfile)
def _release_deleted_students_identity_links(sender, instance, **kwargs):
    """Never leave a crush row claiming a deleted person was verified.

    The original typed evidence is kept; only the verified link is cleared. That
    lets a later correction or a re-registration be handled by a reviewer
    instead of silently retaining a stale identity binding.
    """

    CrushEntry.objects.filter(resolved_student=instance).update(
        identity_status=CrushEntry.ResolutionStatus.PENDING,
        resolved_student=None,
        resolved_at=None,
        resolution_confidence=None,
        resolution_method="",
        resolution_notes="Registered account was deleted; review again.",
    )
    PotentialMatch.objects.filter(
        Q(registered_student=instance) | Q(crush_entry__submitted_by=instance),
        status=PotentialMatch.Status.PENDING,
    ).update(
        status=PotentialMatch.Status.STALE,
        invalidated_reason="Registered account was deleted; proposal retired.",
        scored_at=timezone.now(),
    )


def default_minimum_age() -> int:
    return getattr(settings, "MINIMUM_AGE", 18)


def age_from_dob(dob: dt.date | None) -> int | None:
    if not dob:
        return None
    today = dt.date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))