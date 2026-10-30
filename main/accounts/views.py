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
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode
from django.views.decorators.http import require_POST
import time
import logging

from config.ratelimit import ratelimit

from .emails import check_verification_token, mark_verified, send_verification_email
from .forms import LoginForm, RegisterForm
from .models import EmailVerification, email_is_verified

logger = logging.getLogger(__name__)
User = get_user_model()


def _landing_for(user):
    """Send people wherever they actually belong in the onboarding flow."""
    if not user.is_authenticated:
        return redirect("campus:landing")
    if getattr(user, "student", None) is None:
        return redirect("campus:campus_select")
    return redirect("campus:dashboard")


def _safe_post_next(request, fallback: str) -> str:
    """Only follow a posted ``next`` URL when it stays on this host."""

    target = request.POST.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return fallback


def _verification_status(user):
    """Read the outbox row directly so a stale reverse cache cannot lie."""

    return (
        EmailVerification.objects.filter(user=user)
        .values_list("email_status", flat=True)
        .first()
    )


@ratelimit(key="ip", rate="10/h")
def register(request):
    """'Create your secret profile' (design.md 12)."""
    _t0 = time.perf_counter()
    _cid = getattr(request, 'id', None) or 'na'

    if request.user.is_authenticated:
        return _landing_for(request.user)

    if request.method == "POST":
        _t_form_start = time.perf_counter()
        form = RegisterForm(request.POST)
        if form.is_valid():
            _t_form_end = time.perf_counter()
            _t_user_start = time.perf_counter()
            try:
                with transaction.atomic():
                    user = form.save()
            except IntegrityError:
                # The form check is normally enough, but two simultaneous
                # registrations can still race. The unique username constraint
                # (= the normalized email for normal-length addresses) wins.
                _t_user_end = time.perf_counter()
                form.add_error(
                    "email",
                    "We couldn't create a profile with that email. If it's already "
                    "registered, sign in or reset your password.",
                )
                _t_total = time.perf_counter()
                logger.info(
                    "registration_timing cid=%s status=duplicate form_ms=%.2f user_save_ms=%.2f total_ms=%.2f",
                    _cid,
                    (_t_form_end - _t_form_start) * 1000,
                    (_t_user_end - _t_user_start) * 1000,
                    (_t_total - _t0) * 1000,
                )
            else:
                _t_user_end = time.perf_counter()
                _t_login_start = time.perf_counter()
                login(request, user, backend="accounts.backends.EmailOrUsernameBackend")
                _t_login_end = time.perf_counter()
                # Send the confirmation link after login, so the token (which is
                # bound to the account, not the session) is generated once the
                # account is fully settled. Delivery is best-effort and never
                # blocks onboarding (see accounts/middleware.py for enforcement).
                _t_mail_start = time.perf_counter()
                result = send_verification_email(user, request)
                _t_mail_end = time.perf_counter()
                status = _verification_status(user)
                if result:
                    if status == EmailVerification.EmailStatus.SENT:
                        messages.success(
                            request,
                            "Your secret profile is ready. We sent a confirmation link "
                            "to your college email. Now: which campus are you from?",
                        )
                    elif status == EmailVerification.EmailStatus.FAILED:
                        # Queueing succeeded but delivery did not; never claim it did.
                        messages.warning(
                            request,
                            "Your secret profile is ready, but we could not deliver the "
                            "confirmation email. You can request a new link at any time. "
                            "Now: which campus are you from?",
                        )
                    else:
                        messages.success(
                            request,
                            "Your secret profile is ready. We're sending a confirmation "
                            "link to your college email. Now: which campus are you from?",
                        )
                else:
                    # Never claim an email was sent when it was not even queued.
                    messages.warning(
                        request,
                        "Your secret profile is ready, but we could not queue your "
                        "confirmation email. You can request a new link at any time. "
                        "Now: which campus are you from?",
                    )
                _t_total = time.perf_counter()
                logger.info(
                    "registration_timing cid=%s status=ok form_ms=%.2f user_save_ms=%.2f login_ms=%.2f mail_ms=%.2f total_ms=%.2f",
                    _cid,
                    (_t_form_end - _t_form_start) * 1000,
                    (_t_user_end - _t_user_start) * 1000,
                    (_t_login_end - _t_login_start) * 1000,
                    (_t_mail_end - _t_mail_start) * 1000,
                    (_t_total - _t0) * 1000,
                )
                return redirect("campus:campus_select")
        else:
            _t_form_end = time.perf_counter()
            _t_total = time.perf_counter()
            logger.info(
                "registration_timing cid=%s status=invalid form_ms=%.2f total_ms=%.2f",
                _cid,
                (_t_form_end - _t_form_start) * 1000,
                (_t_total - _t0) * 1000,
            )
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
            "email_status": _verification_status(request.user),
        },
    )


@login_required
@require_POST
@ratelimit(key="user", rate="5/h")
def resend_verification(request):
    result = send_verification_email(request.user, request)
    status = _verification_status(request.user)
    if email_is_verified(request.user) or result.reason == "already_verified":
        messages.info(request, "Your email is already confirmed.")
    elif result.reason == "already_queued":
        messages.info(
            request,
            "A confirmation email is already on its way. Check your inbox in a moment.",
        )
    elif result:
        if status == EmailVerification.EmailStatus.SENT:
            messages.success(
                request,
                "Your confirmation email was sent. Check your inbox in a moment.",
            )
        elif status == EmailVerification.EmailStatus.FAILED:
            messages.warning(
                request,
                "We queued your confirmation email but could not deliver it. "
                "It will be retried automatically; you can also try again shortly.",
            )
        else:
            messages.success(
                request,
                "Your confirmation email is queued and will be sent shortly. "
                "Check your inbox in a moment.",
            )
    elif result.reason == "throttled":
        messages.info(request, "We just sent one. Please wait a minute before trying again.")
    else:
        messages.error(
            request,
            "We could not queue that email just now. Please try again in a moment.",
        )
    return redirect(
        _safe_post_next(request, reverse("accounts:verify_email_notice"))
    )