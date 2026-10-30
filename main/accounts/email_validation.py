"""Conservative email typo detection for registration.

Only an *exact* match against the configured domain mapping produces a
suggestion. There is deliberately no fuzzy matching here: a student with a
legitimate custom domain must never be pushed away from their real address.
"""

from __future__ import annotations

from django.conf import settings

#: Used when ``settings.EMAIL_DOMAIN_SUGGESTIONS`` is not defined.
DEFAULT_DOMAIN_SUGGESTIONS = {
    "gmial.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gnail.com": "gmail.com",
    "yaho.com": "yahoo.com",
    "hotnail.com": "hotmail.com",
    "hotmai.com": "hotmail.com",
    "outlok.com": "outlook.com",
    "outllok.com": "outlook.com",
}


def normalize_email(email: str) -> str:
    """Match the project's existing registration convention: trim + lowercase."""

    return (email or "").strip().lower()


def _domain_suggestions() -> dict[str, str]:
    configured = getattr(settings, "EMAIL_DOMAIN_SUGGESTIONS", None)
    return DEFAULT_DOMAIN_SUGGESTIONS if configured is None else configured


def split_email(email: str) -> tuple[str, str]:
    local, separator, domain = normalize_email(email).rpartition("@")
    if not separator or not local or not domain:
        return "", ""
    return local, domain


def suggest_email_correction(email: str) -> str | None:
    """Return a corrected address only for an exact known misspelled domain.

    ``None`` means either the address is fine or we do not know it well enough
    to make a suggestion. The caller decides whether to ask the student.
    """

    local, domain = split_email(email)
    if not local:
        return None

    replacement = _domain_suggestions().get(domain)
    if not replacement:
        return None

    replacement = str(replacement).strip().lower()
    if not replacement or "@" in replacement or "." not in replacement:
        return None

    corrected = f"{local}@{replacement}"
    if corrected == normalize_email(email):
        return None
    return corrected
