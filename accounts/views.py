from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy

from .forms import LoginForm, RegisterForm


def _landing_for(user):
    """Send people wherever they actually belong in the onboarding flow."""
    if not user.is_authenticated:
        return redirect("campus:landing")
    if getattr(user, "student", None) is None:
        return redirect("campus:campus_select")
    return redirect("campus:dashboard")


def register(request):
    """'Create your secret profile' (design.md 12)."""

    if request.user.is_authenticated:
        return _landing_for(request.user)

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="accounts.backends.EmailOrUsernameBackend")
            messages.success(
                request,
                "Your secret profile is ready. One more thing: which campus are you from?",
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