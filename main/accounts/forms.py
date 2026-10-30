import hashlib

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .email_validation import normalize_email, suggest_email_correction

User = get_user_model()
EMAIL_MAX_LENGTH = User._meta.get_field("email").max_length
USERNAME_MAX_LENGTH = User._meta.get_field("username").max_length


def username_for_email(email: str) -> str:
    """Return a stable username that the unique constraint can protect.

    Normal-length addresses use the normalized email itself, matching the
    project's existing convention. Longer addresses cannot fit in the username
    column, so a deterministic digest is used instead of a random UUID: two
    simultaneous registrations for the same address then collide on the
    username constraint instead of both succeeding.
    """

    if len(email) <= USERNAME_MAX_LENGTH:
        return email
    digest = hashlib.sha256(email.encode("utf-8")).hexdigest()
    return f"email-{digest}"


class RegisterForm(UserCreationForm):
    """Step 3 of onboarding: the login that holds your private campus ID."""

    email = forms.EmailField(
        required=True, label="College email", max_length=EMAIL_MAX_LENGTH
    )
    agree = forms.BooleanField(
        required=True,
        label="I agree to the Terms and the Community Rules",
        error_messages={"required": "Please accept the terms to continue."},
    )
    confirm_email_typo = forms.BooleanField(
        required=False,
        label="No, my email address is correct",
        widget=forms.CheckboxInput(attrs={"class": "check"}),
    )

    class Meta:
        model = User
        fields = ["email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.email_suggestion = None
        self.fields["email"].widget.attrs.update(
            {
                "class": "input",
                "placeholder": "you@college.edu",
                "autocomplete": "email",
                "inputmode": "email",
                "autocapitalize": "none",
                "spellcheck": "false",
            }
        )

        # Accepting the suggestion is an explicit POST action. Apply it to the
        # bound data *before* validation so the form redisplays the corrected
        # address (rather than silently rewriting it at save time).
        if self.is_bound and self.data.get("use_suggested_email"):
            suggestion = suggest_email_correction(self.data.get("email", ""))
            if suggestion:
                data = self.data.copy()
                data["email"] = suggestion
                self.data = data
        for name in ("password1", "password2"):
            self.fields[name].widget.attrs.update(
                {
                    "class": "input",
                    "placeholder": (
                        "Create a password" if name == "password1" else "Repeat password"
                    ),
                    "autocomplete": "new-password",
                }
            )
        self.fields["agree"].widget.attrs["class"] = "check"

    def clean_email(self):
        email = normalize_email(self.cleaned_data["email"])
        suggestion = suggest_email_correction(email)
        if suggestion and not self.data.get("confirm_email_typo"):
            self.email_suggestion = suggestion
            raise forms.ValidationError(
                f"Did you mean {suggestion}? If your address is correct, "
                "tick the box below to confirm it."
            )

        if User.objects.filter(email__iexact=email).exists():
            # Keep the wording neutral rather than confirming that an account
            # exists for this address (account-enumeration resistance).
            raise forms.ValidationError(
                "We couldn't create a profile with that email. If it's already "
                "registered, sign in or reset your password."
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"]
        user.email = email
        user.username = username_for_email(email)
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "College email"
        self.fields["username"].widget.attrs.update(
            {
                "class": "input",
                "placeholder": "you@college.edu",
                "autocomplete": "email",
                "inputmode": "email",
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "class": "input",
                "placeholder": "Password",
                "autocomplete": "current-password",
            }
        )
        self.error_messages["invalid_login"] = (
            "Hmm, that email and password did not match."
        )
        self.error_messages["inactive"] = "This account has been deactivated."