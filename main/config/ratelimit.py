"""Dependency-free, cache-backed rate limiting for sensitive actions.

The product has no third-party throttling dependency and does not need one for
its threat model: registration, login, password resets, crush writes and
abuse reports are all low-volume actions that a small fixed-window counter can
protect (requirements 3/18).

Usage::

    from config.ratelimit import ratelimit

    @ratelimit(key="ip", rate="5/m")
    def login_view(request): ...

    @ratelimit(key="user", rate="30/h")
    def add_crush(request): ...

The backend is :mod:`django.core.cache`, so the store that is configured for
the project decides how far the counters travel. The default
``LocMemCache`` is per-process, which is fine for local development and a
single worker; production should point ``CACHES`` at Redis or Memcached so the
limit is shared across workers. This is documented in ``docs/deployment.md``.

Failures are open: if the cache is misconfigured or evicts the counter, the
request is allowed through rather than locking every student out.
"""

from __future__ import annotations

import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

_PERIODS = {
    "s": 1,
    "m": 60,
    "h": 60 * 60,
    "d": 60 * 60 * 24,
}

TOO_MANY_MESSAGE = "Too many attempts. Please wait a moment and try again."


def client_ip(request) -> str:
    """Best-effort client address.

    ``X-Forwarded-For`` is trusted only because the proxy in front of the app
    is expected to overwrite it (see ``docs/deployment.md``); an attacker who
    can reach the app directly cannot forge ``REMOTE_ADDR``.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def parse_rate(rate: str) -> tuple[int, int]:
    """``"5/m"`` -> ``(5, 60)``."""
    amount, _, period = rate.partition("/")
    try:
        limit = int(amount)
    except ValueError:
        limit = 1
    seconds = _PERIODS.get((period or "m").lower(), 60)
    return max(1, limit), seconds


def _identifier(request, key: str) -> str:
    if key == "user":
        if request.user.is_authenticated:
            return f"u{request.user.pk}"
        return f"ip{client_ip(request)}"
    if key == "post":
        # A coarse fingerprint: the address plus the target path. Used where a
        # single account may legitimately act from one address (e.g. reports).
        return f"ip{client_ip(request)}:{request.path}"
    return f"ip{client_ip(request)}"


def ratelimit(key: str = "ip", rate: str = "10/m", method: str = "POST", block: bool = True):
    """Decorator factory. Only throttles ``method`` requests unless method is ``None``."""

    limit, window = parse_rate(rate)

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            # ``RATELIMIT_ENABLE`` is turned off for the test suite so a shared
            # process cache never makes results order-dependent. Production code
            # leaves it on; docs/deployment.md explains the cache backend.
            if not getattr(settings, "RATELIMIT_ENABLE", True):
                return view(request, *args, **kwargs)
            if method and request.method != method:
                return view(request, *args, **kwargs)

            ident = _identifier(request, key)
            bucket = int(time.time()) // window
            cache_key = f"rl:{view.__module__}.{view.__name__}:{ident}:{bucket}"

            try:
                # add() is atomic on every supported backend, so the counter is
                # never lost to a read-modify-write race between workers.
                if cache.add(cache_key, 1, timeout=window + 1):
                    count = 1
                else:
                    count = cache.incr(cache_key)
            except Exception:  # pragma: no cover - fail open on cache trouble
                count = 1

            if block and count > limit:
                response = HttpResponse(
                    TOO_MANY_MESSAGE, status=429, content_type="text/plain"
                )
                response["Retry-After"] = str(window)
                return response
            return view(request, *args, **kwargs)

        wrapper.ratelimit = (key, rate)
        return wrapper

    return decorator
