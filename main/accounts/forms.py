import uuid

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class RegisterForm(UserCreationForm):
    """Step 3 of onboarding: the login that holds your private campus ID."""

    email = forms.EmailField(required=True, label="College email")
    agree = forms.BooleanField(
        required=True,
        label="I agree to the Terms and the Community Rules",
        error_messages={"required": "Please accept the terms to continue."},
    )

    class Meta:
        model = User
        fields = ["email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {
                "class": "input",
                "placeholder": "you@college.edu",
                "autocomplete": "email",
                "inputmode": "email",
            }
        )
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
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "That email already has a campus profile. Try signing in."
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"]
        user.email = email
        user.username = email[:150] if len(email) <= 150 else uuid.uuid4().hex
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