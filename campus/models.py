from __future__ import annotations

import datetime as dt
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

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
        indexes = [models.Index(fields=["name"]), models.Index(fields=["city"])]

    def __str__(self) -> str:
        return self.display_name

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
            models.Index(fields=["college", "full_name"]),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} · {self.college.name}"

    def save(self, *args, **kwargs):
        self.normalized_roll_number = normalize_roll_number(self.roll_number)
        if not self.normalized_roll_number:
            raise ValidationError({"roll_number": "Enter your roll number."})
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

    This is deliberately **not** a relation to ``User`` or ``StudentProfile``.
    The crush is usually someone who has never opened the site, so all we can
    store is what the submitter happens to know (requirements 4/5).

    ``priority`` is an internal 1..3 ordering. It exists only so the admin can
    sanity-check a submission during verification. It must never be rendered,
    emailed, or exposed to either student (requirements 2/13).
    """

    submitted_by = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="crush_entries"
    )
    priority = models.PositiveSmallIntegerField(
        help_text="Internal ordering 1-3. Never shown to either student."
    )
    full_name = models.CharField(max_length=255)
    roll_number = models.CharField(max_length=100)
    normalized_roll_number = models.CharField(max_length=100, db_index=True)
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
        ]
        indexes = [
            # The identity lookup the matcher always uses (requirements 7/8).
            models.Index(fields=["college", "normalized_roll_number"]),
            models.Index(fields=["submitted_by", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"#{self.priority} · {self.full_name}"

    def save(self, *args, **kwargs):
        self.normalized_roll_number = normalize_roll_number(self.roll_number)
        if not self.normalized_roll_number:
            raise ValidationError({"roll_number": "Enter the roll number."})
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.priority and not 1 <= self.priority <= MAX_CRUSHES:
            raise ValidationError({"priority": "Choose between 1 and 3."})
        if self.submitted_by_id and self.submitted_by_id == getattr(
            self, "matched_student_id", None
        ):
            raise ValidationError("You cannot enter yourself as a crush.")

    @property
    def masked_roll_number(self) -> str:
        roll = self.roll_number
        if len(roll) <= 3:
            return "•••"
        return "•••" + roll[-3:]

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
        return self.user_b_consented if self.user_a_id == student.pk else self.user_a_consented

    def record_consent(self, student: StudentProfile) -> None:
        if self.user_a_id == student.pk:
            self.user_a_consented = True
        else:
            self.user_b_consented = True

    def save(self, *args, **kwargs):
        if self.user_a_id and self.user_b_id and self.user_a_id > self.user_b_id:
            self.user_a, self.user_b = self.user_b, self.user_a
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
        return self.status != self.Status.PENDING

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

    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.SYSTEM)
    message = models.CharField(max_length=200)
    url = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["student", "is_read"])]

    def __str__(self) -> str:
        return self.message


def default_minimum_age() -> int:
    return getattr(settings, "MINIMUM_AGE", 18)


def age_from_dob(dob: dt.date | None) -> int | None:
    if not dob:
        return None
    today = dt.date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))