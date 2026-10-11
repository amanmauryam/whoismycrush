from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST

from config.ratelimit import ratelimit

from .emails import check_verification_token, mark_verified, send_verification_email
from .forms import LoginForm, RegisterForm
from .models import email_is_verified

User = get_user_model()


def _landing_for(user):
    """Send people wherever they actually belong in the onboarding flow."""
    if not user.is_authenticated:
        return redirect("campus:landing")
    if getattr(user, "student", None) is None:
        return redirect("campus:campus_select")
    return redirect("campus:dashboard")


@ratelimit(key="ip", rate="10/h")
def register(request):
    """'Create your secret profile' (design.md 12)."""

    if request.user.is_authenticated:
        return _landing_for(request.user)

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="accounts.backends.EmailOrUsernameBackend")
            # Send the confirmation link after login, so the token (which is
            # bound to the account, not the session) is generated once the
            # account is fully settled. Delivery is best-effort and never blocks
            # onboarding (see accounts/middleware.py for hard enforcement).
            send_verification_email(user, request)
            messages.success(
                request,
                "Your secret profile is ready. We've emailed you a confirmation link. "
                "Now: which campus are you from?",
            )
            return redirect("campus:campus_select")
    else:
        form = RegisterForm()

    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
            "page_title": "Create your secret profile",
            "meta_description": (
                "Just enough information to find the right person. Nothing more."
            ),
            "canonical_path": "/register/",
            "step": 3,
        },
    )


@method_decorator(ratelimit(key="ip", rate="15/m"), name="dispatch")
class AccountLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = False

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return _landing_for(request.user)
        return super().get(request, *args, **kwargs)

    def get_success_url(self):
        user = self.request.user
        if getattr(user, "student", None) is None:
            return reverse("campus:campus_select")
        return reverse("campus:dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Sign in"
        context["canonical_path"] = "/login/"
        context["meta_description"] = "Sign in to open your secret desk."
        return context


class AccountLogoutView(LogoutView):
    next_page = reverse_lazy("campus:landing")


@method_decorator(ratelimit(key="ip", rate="5/h"), name="dispatch")
class ForgotPasswordView(PasswordResetView):
    template_name = "accounts/forgot_password.html"
    email_template_name = "accounts/email_reset.txt"
    subject_template_name = "accounts/email_reset_subject.txt"
    success_url = reverse_lazy("accounts:forgot_password_done")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Reset your password"
        context["canonical_path"] = "/forgot-password/"
        return context


class ForgotPasswordDoneView(PasswordResetDoneView):
    template_name = "accounts/forgot_password_done.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Check your email"
        context["canonical_path"] = "/forgot-password/sent/"
        return context


class ResetPasswordConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Choose a new password"
        return context


class ResetPasswordCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Password updated"
        return context


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


def _user_from_uidb64(uidb64):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None


def verify_email(request, uidb64, token):
    """Confirmation link target.

    GET shows a one-tap confirmation (never auto-confirms, so email link
    scanners cannot verify an address on the student's behalf); POST performs
    the confirmation.
    """

    user = _user_from_uidb64(uidb64)
    valid = check_verification_token(user, token)

    if request.method == "POST":
        if valid:
            first_time = mark_verified(user)
            if first_time:
                messages.success(request, "Email confirmed. Welcome to your campus.")
            else:
                messages.info(request, "That email was already confirmed.")
            if request.user.is_authenticated:
                return _landing_for(request.user)
            return redirect("accounts:login")
        messages.error(
            request, "That confirmation link is invalid or has expired. Request a new one."
        )
        return redirect("accounts:login")

    return render(
        request,
        "accounts/verify_email.html",
        {
            "valid": valid,
            "uidb64": uidb64,
            "token": token,
            "page_title": "Confirm your email",
            "meta_description": "Confirm the email on your WhoIsMyCrush account.",
        },
    )


@login_required
def verify_email_notice(request):
    """Holding page shown when verification is enforced and still pending."""

    if email_is_verified(request.user):
        return _landing_for(request.user)
    return render(
        request,
        "accounts/verify_email_notice.html",
        {
            "page_title": "Confirm your email",
            "meta_description": "One quick step before you continue.",
            "can_index": False,
            "email_verification_pending_page": True,
        },
    )


@login_required
@require_POST
@ratelimit(key="user", rate="5/h")
def resend_verification(request):
    if email_is_verified(request.user):
        messages.info(request, "Your email is already confirmed.")
    elif send_verification_email(request.user, request):
        messages.success(request, "Sent. Check your inbox for the confirmation link.")
    else:
        messages.info(request, "We just sent one. Please wait a minute before trying again.")
    return redirect(request.POST.get("next") or reverse("accounts:verify_email_notice"))