"""Central eligibility policy for identity resolution and mutual matching.

The scoring modules keep their numerical weights in code because changing a
weight changes the meaning of a stored score. Which *fields* are allowed to
block an automatic path is an operational decision, so it is configurable here.

Hard fields reject a pair/candidate outright. Soft fields only reduce the
confidence and are shown to the reviewer. Missing values are never conflicts.
"""

from __future__ import annotations

from django.conf import settings

DEFAULT_MATCH_HARD_FIELDS = ("course", "year", "section")
DEFAULT_IDENTITY_HARD_FIELDS = ("course", "year", "section")


def _fields(name: str, default: tuple[str, ...]) -> frozenset[str]:
    raw = getattr(settings, name, default)
    if isinstance(raw, str):
        raw = raw.split(",")
    return frozenset(str(item).strip().lower() for item in raw if str(item).strip())


def match_hard_fields() -> frozenset[str]:
    return _fields("MATCH_HARD_CONFLICT_FIELDS", DEFAULT_MATCH_HARD_FIELDS)


def identity_hard_fields() -> frozenset[str]:
    return _fields("IDENTITY_HARD_CONFLICT_FIELDS", DEFAULT_IDENTITY_HARD_FIELDS)


def min_match_confidence() -> float:
    return float(getattr(settings, "MATCH_MIN_CONFIDENCE", 40.0))


def match_requires_unresolved_roll() -> bool:
    return bool(getattr(settings, "MATCH_REQUIRE_ROLL_FOR_UNRESOLVED", True))
