"""Optional enforcement of email verification.

Verification is **soft by default**: an unverified student can still use the
product while a banner nudges them, because blocking onboarding on an email
round-trip loses genuinely interested users and the site is not a bank.

Deployments that want it hard can set ``EMAIL_VERIFICATION_REQUIRED=True`` and
every authenticated, unverified, non-staff account is redirected to a small
"confirm your email" holding page until it is done. The allow-list below is
deliberately tiny: the verification pages themselves, logout, auth endpoints,
static files and the admin (which staff may need to confirm addresses from).
"""

from __future__ import annotations

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from .models import email_is_verified

ALLOWED_PREFIXES = (
    "/verify-email/",
    "/logout/",
    "/login/",
    "/register/",
    "/forgot-password/",
    "/reset/",
    "/admin/",
)
ALLOWED_EXACT = ("/robots.txt", "/sitemap.xml", "/favicon.ico")


class EmailVerificationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._must_verify(request):
            return redirect(reverse("accounts:verify_email_notice"))
        return self.get_response(request)

    def _must_verify(self, request) -> bool:
        if not getattr(settings, "EMAIL_VERIFICATION_REQUIRED", False):
            return False
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or user.is_staff:
            return False
        if email_is_verified(user):
            return False
        path = request.path
        if path in ALLOWED_EXACT or path.startswith(ALLOWED_PREFIXES):
            return False
        if path.startswith(settings.STATIC_URL or "/static/") or path.startswith(
            settings.MEDIA_URL or "/media/"
        ):
            return False
        return True
