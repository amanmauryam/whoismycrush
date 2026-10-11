"""Auth-only models for the accounts app.

The login itself is Django's built-in ``User``; the private campus identity
lives in ``campus.StudentProfile``. The one thing that belongs here is the
email-verification state, because it describes the *account*, not the campus
identity, and it must exist the moment the account is created -- before any
campus has been chosen.
"""

from django.conf import settings
from django.db import models


class EmailVerification(models.Model):
    """One row per account. Verified state is a timestamp, not a bare bool, so
    we keep an audit trail of *when* an address was confirmed (requirements 3)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verification",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(
        null=True, blank=True, help_text="Last verification email sent."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "email verification"
        verbose_name_plural = "email verifications"

    def __str__(self) -> str:
        state = "verified" if self.is_verified else "pending"
        return f"user #{self.user_id} ({state})"

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None


def email_is_verified(user) -> bool:
    """True only when the account exists and its address was confirmed."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    record = getattr(user, "email_verification", None)
    return bool(record and record.verified_at)
