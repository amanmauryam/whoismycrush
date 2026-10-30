from __future__ import annotations

import datetime as dt

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from .models import (
    MAX_CRUSHES,
    Block,
    College,
    CollegeInvite,
    CrushEntry,
    Report,
    StudentProfile,
    normalize_name,
    normalize_roll_number,
)


class CampusSearchForm(forms.Form):
    """The free-text filter on the campus picker (design.md 14)."""

    q = forms.CharField(
        required=False,
        label="Search your college",
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search your college...",
                "autocomplete": "off",
                "autocapitalize": "words",
                "enterkeyhint": "search",
            }
        ),
    )

    def clean_q(self):
        return " ".join(self.cleaned_data["q"].split())


class CollegeCreateForm(forms.Form):
    """Add a campus that isn't in the picker yet (India has thousands).

    Kept open to anonymous visitors on purpose: a student picks their campus
    *before* signing up, so the person who discovers a missing college is
    usually not logged in yet. The created ``College`` is active immediately,
    so the next candidate who searches finds it.
    """

    name = forms.CharField(
        max_length=180,
        label="College name",
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. St. Xavier's College",
                "autocomplete": "organization",
                "autocapitalize": "words",
            }
        ),
    )
    city = forms.CharField(
        max_length=120,
        required=False,
        label="City",
        widget=forms.TextInput(
            attrs={"placeholder": "City (optional)", "autocomplete": "address-level2"}
        ),
    )
    state = forms.CharField(
        max_length=120,
        required=False,
        label="State",
        widget=forms.TextInput(
            attrs={"placeholder": "State (optional)", "autocomplete": "address-level1"}
        ),
    )

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if len(name) < 3:
            raise ValidationError("Enter the full name of your college.")
        return name

    def clean_city(self):
        return " ".join((self.cleaned_data.get("city") or "").split())

    def clean_state(self):
        return " ".join((self.cleaned_data.get("state") or "").split())


class CampusChoiceForm(forms.Form):
    """Step 1 of onboarding. Identity never crosses a campus boundary."""

    college = forms.ModelChoiceField(
        queryset=College.objects.none(),
        label="Your campus",
        empty_label="Select your campus",
        error_messages={"invalid_choice": "Pick the campus you study at."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["college"].queryset = College.objects.filter(is_active=True)
        self.fields["college"].widget.attrs.update({"class": "input"})

    def clean_college(self):
        college = self.cleaned_data["college"]
        if not college.is_active:
            raise ValidationError("That campus is not accepting students right now.")
        return college


class StudentIdentityForm(forms.ModelForm):
    """Step 2 of onboarding: the private campus ID (design.md 13/15)."""

    age_confirmation = forms.BooleanField(
        required=True,
        label="I confirm I am 18 or older",
        error_messages={"required": "You must be 18 or older to use WhoIsMyCrush."},
    )

    class Meta:
        model = StudentProfile
        fields = [
            "full_name",
            "roll_number",
            "course",
            "year",
            "section",
            "gender",
            "date_of_birth",
            "department",
            "nickname",
        ]
        widgets = {
            "full_name": forms.TextInput(
                attrs={"placeholder": "Aman Kumar", "autocomplete": "name"}
            ),
            "roll_number": forms.TextInput(
                attrs={
                    "placeholder": "23BCA104",
                    "autocapitalize": "characters",
                    "spellcheck": "false",
                }
            ),
            "date_of_birth": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "department": forms.TextInput(
                attrs={"placeholder": "Optional", "autocomplete": "off"}
            ),
            "nickname": forms.TextInput(
                attrs={"placeholder": "Optional", "maxlength": "60"}
            ),
        }

    def __init__(self, *args, user=None, college=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.college = college or getattr(user, "student", None)
        self.fields["date_of_birth"].input_formats = ["%Y-%m-%d"]
        for name in ("full_name", "course", "year"):
            self.fields[name].widget.attrs["class"] = "input"
        for name in ("roll_number", "section", "gender", "date_of_birth", "nickname"):
            self.fields[name].widget.attrs["class"] = "input"
        self.fields["date_of_birth"].label = "Date of birth"
        self.fields["department"].label = "Department (optional)"
        self.fields["department"].required = False
        self.fields["nickname"].label = "Profile nickname (optional)"
        self.fields["nickname"].required = False
        if self.college:
            self.fields["roll_number"].help_text = (
                f"As printed on your {self.college.name} ID card. "
                "Only the last 3 digits are ever shown to others."
            )

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if len(name) < 3:
            raise ValidationError("Enter your full name.")
        return name

    def clean_roll_number(self):
        roll = (self.cleaned_data.get("roll_number") or "").strip().upper()
        if not normalize_roll_number(roll):
            raise ValidationError("Enter the roll number printed on your ID card.")
        return roll

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")
        if dob:
            today = dt.date.today()
            if dob > today:
                raise ValidationError("Date of birth cannot be in the future.")
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            minimum = getattr(settings, "MINIMUM_AGE", 18)
            if age < minimum:
                raise ValidationError(
                    f"WhoIsMyCrush is for students 18 and above. You need to be {minimum}."
                )
        return dob

    def clean(self):
        cleaned = super().clean()
        college = self.college
        roll = cleaned.get("roll_number")
        if college and roll:
            clash = StudentProfile.objects.filter(
                college=college, normalized_roll_number=normalize_roll_number(roll)
            ).exclude(pk=self.instance.pk)
            if clash.exists():
                self.add_error(
                    "roll_number",
                    "That roll number is already registered at this campus. "
                    "Only one campus identity per student is allowed.",
                )
        return cleaned

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.college = self.college
        if commit:
            profile.save()
        return profile


class CrushEntryForm(forms.ModelForm):
    """Hand-typed crush details for one of the three slots (requirements 3/21).

    Every field mirrors ``StudentProfile`` so the matcher can compare them
    directly. Nothing here resolves to a ``User``: the crush does not need an
    account (requirements 1/5).
    """

    class Meta:
        model = CrushEntry
        fields = [
            "full_name",
            "roll_number",
            "course",
            "year",
            "section",
            "college",
            "department",
            "nickname",
        ]
        widgets = {
            "full_name": forms.TextInput(
                attrs={
                    "placeholder": "Priya Sharma",
                    "autocomplete": "off",
                    "autocapitalize": "words",
                }
            ),
            "roll_number": forms.TextInput(
                attrs={
                    "placeholder": "27",
                    "autocomplete": "off",
                    "autocapitalize": "characters",
                    "spellcheck": "false",
                }
            ),
            "section": forms.TextInput(
                attrs={"placeholder": "A", "autocomplete": "off", "maxlength": "50"}
            ),
            "department": forms.TextInput(
                attrs={"placeholder": "Optional", "autocomplete": "off"}
            ),
            "nickname": forms.TextInput(
                attrs={"placeholder": "Optional", "autocomplete": "off"}
            ),
        }

    def __init__(self, *args, author=None, priority=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.author = author
        self.priority = priority
        # Make the ownership visible to ``CrushEntry.clean`` during form
        # validation; ``save`` still writes the same values.
        if author is not None:
            self.instance.submitted_by = author
        if priority is not None:
            self.instance.priority = priority
        self.fields["college"].queryset = College.objects.filter(is_active=True)
        self.fields["college"].empty_label = "Select their campus"
        self.fields["college"].required = True
        self.fields["section"].required = False
        self.fields["department"].required = False
        self.fields["nickname"].required = False

        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "input")

        self.fields["full_name"].label = "Full name"
        self.fields["roll_number"].label = "Roll number (optional)"
        self.fields["roll_number"].help_text = (
            "Leave this blank if you are not sure. We will keep checking safely "
            "as new students join; nothing is revealed unless a match is confirmed."
        )
        self.fields["roll_number"].required = False
        self.fields["department"].label = "Department (optional)"
        self.fields["nickname"].label = "Known nickname (optional)"

        # The submitter's own campus is the common case, so make it the
        # default rather than forcing a re-pick every slot.
        if author is not None and not self.is_bound:
            self.fields["college"].initial = author.college_id

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if len(normalize_name(name)) < 2:
            raise ValidationError("Enter the name you know them by.")
        return name

    def clean_roll_number(self):
        # Roll numbers are optional evidence, not the identity itself. An
        # unknown or mistyped roll must never discard the rest of the entry.
        return (self.cleaned_data.get("roll_number") or "").strip().upper()

    def clean_section(self):
        return " ".join((self.cleaned_data.get("section") or "").split()).upper()

    def clean_department(self):
        return " ".join((self.cleaned_data.get("department") or "").split())

    def clean_nickname(self):
        return " ".join((self.cleaned_data.get("nickname") or "").split())

    def clean(self):
        cleaned = super().clean()
        author = self.author
        college = cleaned.get("college")
        roll = cleaned.get("roll_number")

        if author is not None and college and college.pk != author.college_id:
            self.add_error(
                "college",
                "Crushes can only be entered on your own campus.",
            )

        # You cannot enter yourself as one of your own crushes.
        if author is not None and college and roll:
            own_roll = normalize_roll_number(author.roll_number)
            if college.pk == author.college_id and normalize_roll_number(roll) == own_roll:
                self.add_error("roll_number", "That is your own roll number.")

        # Duplicate active target detection lives on ``CrushEntry.clean`` so the
        # admin and every other ModelForm path get the same safeguard.
        return cleaned

    def save(self, commit=True):
        entry = super().save(commit=False)
        entry.submitted_by = self.author
        entry.priority = self.priority
        if commit:
            entry.save()
        return entry


class CampusIdForm(forms.ModelForm):
    """Edit your Campus ID. Changing a verified roll number needs re-verification."""

    class Meta:
        model = StudentProfile
        fields = [
            "full_name",
            "roll_number",
            "nickname",
            "course",
            "year",
            "section",
            "department",
            "gender",
        ]
        labels = {
            "nickname": "Profile nickname (optional)",
            "department": "Department (optional)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"
        self.fields["roll_number"].widget.attrs.update(
            {"autocapitalize": "characters", "spellcheck": "false"}
        )
        self.fields["roll_number"].help_text = (
            "Only the last 3 digits are ever shown to others."
        )
        self.fields["nickname"].required = False
        self.fields["department"].required = False
        self._original_normalized_roll = normalize_roll_number(
            self.instance.roll_number
        )

    def clean_roll_number(self):
        roll = (self.cleaned_data.get("roll_number") or "").strip().upper()
        if not normalize_roll_number(roll):
            raise ValidationError("Enter the roll number printed on your ID card.")
        return roll

    def clean(self):
        cleaned = super().clean()
        roll = cleaned.get("roll_number")
        if roll and self.instance.college_id:
            clash = (
                StudentProfile.objects.filter(
                    college_id=self.instance.college_id,
                    normalized_roll_number=normalize_roll_number(roll),
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if clash:
                self.add_error(
                    "roll_number",
                    "That roll number is already registered at this campus. "
                    "Only one campus identity per student is allowed.",
                )
        return cleaned

    def save(self, commit=True):
        profile = super().save(commit=False)
        roll_changed = (
            normalize_roll_number(profile.roll_number) != self._original_normalized_roll
        )
        if roll_changed and self.instance.is_verified:
            profile.is_verified = False
        if commit:
            profile.save()
        return profile


class PotentialMatchNotesForm(forms.Form):
    """Admin review note. Persisted into the audit trail (requirement 25)."""

    admin_notes = forms.CharField(
        required=True,
        min_length=3,
        max_length=300,
        widget=forms.Textarea(
            attrs={
                "rows": "4",
                "placeholder": "Why you approved or rejected this.",
                "required": "required",
            }
        ),
        label="Review notes",
        help_text="Required. Stored in the audit trail, never shown to students.",
    )

    def clean_admin_notes(self):
        notes = " ".join(self.cleaned_data["admin_notes"].split())
        if len(notes) < 3:
            raise ValidationError("Add a short reason for this decision.")
        return notes


class PrivacySettingsForm(forms.Form):
    """Placeholder retained so the privacy centre template keeps its contract.

    There are deliberately no toggles left. With student search removed there is
    nothing to hide yourself from -- your list is unlistable either way. The
    real privacy controls are the destructive actions further down that page
    (wipe your crush list, delete your account).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class RevealChoiceForm(forms.Form):
    CHOICES = [
        ("reveal", "Reveal my identity"),
        ("anonymous", "Keep anonymous"),
    ]
    choice = forms.ChoiceField(choices=CHOICES, widget=forms.RadioSelect)


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "detail"]
        widgets = {
            "detail": forms.Textarea(
                attrs={"rows": "3", "placeholder": "Add anything that helps (optional)"}
            )
        }
        labels = {"detail": "Details"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].widget.attrs["class"] = "input"
        self.fields["detail"].required = False
        self.fields["detail"].widget.attrs["class"] = "input"


class BlockForm(forms.Form):
    confirm = forms.BooleanField(
        required=True, label="I confirm I want to block this student"
    )


class CollegeInviteForm(forms.ModelForm):
    class Meta:
        model = CollegeInvite
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "your.email@college.edu",
                    "autocomplete": "email",
                    "class": "input",
                }
            )
        }
        labels = {"email": "Notify me when this campus opens (optional)"}
        help_text = {
            "email": "We only email you when your campus is live. Never shared."
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False


def blocked_between(student: StudentProfile) -> list:
    """Ids hidden from ``student``: people they blocked and their blockers."""
    if not student or not student.pk:
        return []
    outgoing = Block.objects.filter(blocker=student).values_list("blocked_id", flat=True)
    incoming = Block.objects.filter(blocked=student).values_list("blocker_id", flat=True)
    return list({*outgoing, *incoming})


def next_free_priority(student: StudentProfile) -> int:
    """Lowest unused slot in 1..MAX_CRUSHES, else the next free one."""
    used = set(
        CrushEntry.objects.active()
        .filter(submitted_by=student)
        .values_list("priority", flat=True)
    )
    for slot in range(1, MAX_CRUSHES + 1):
        if slot not in used:
            return slot
    return MAX_CRUSHES


def remaining_slots(student: StudentProfile) -> int:
    return max(0, MAX_CRUSHES - active_entry_count(student))


def active_entry_count(student: StudentProfile) -> int:
    if not student or not student.pk:
        return 0
    return CrushEntry.objects.active().filter(submitted_by=student).count()