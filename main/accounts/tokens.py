"""Token generator for the email-verification link.

Django's ``PasswordResetTokenGenerator`` is a good, constant-time base but its
default hash mixes in ``last_login``, so auto-logging a student in right after
registration would immediately invalidate the link we just emailed them. This
subclass hashes only the primary key, the email address and the timestamp, so a
link keeps working until ``PASSWORD_RESET_TIMEOUT`` and burns the moment the
address changes.
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "accounts.tokens.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.email or ''}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()
