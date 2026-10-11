# WhoIsMyCrush

A privacy-first, college-only **mutual crush** platform. You secretly add up
to three people from your own campus; you find out **only** when one of them
secretly added you too — and only after a human verifies both sides.

- **No student search.** Crushes are typed by hand, never picked from a list.
- **No public directory.** Campus boundaries exist for matching, not browsing.
- **No notification until it's mutual and verified.**
- **Priority is internal only.** Not even a matched student sees your order.

## Start quickly

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_posts        # launch blog guides (idempotent)
python manage.py createsuperuser
python manage.py runserver
```

Demo people and a verified mutual match (optional):

```powershell
python manage.py seed_demo         # a college + several campus IDs
python manage.py seed_match        # one admin-verified mutual crush
```

## Tests

```powershell
python manage.py test
```

`RATELIMIT_ENABLE` defaults to **off** under the test runner so shared cache
counters never make results order-dependent. Everything else — rate limiting,
email verification, sanitized blog rendering — is covered.

## The one non-negotiable rule

A match is two real people at the same college, both of whom chose each other,
independently confirmed by a verifier. Everything that would weaken that
(cross-campus matching, name-only matching, auto-approval, public lists,
exposing priority, telling someone they were picked) is deliberately absent.

## Environment

Everything the app reads lives in `.env` (gitignored — `.env.*` is ignored and
there is no committed template). Use the commented blocks inside `.env` as the
guide. Notable switches:

| Var | Default | Meaning |
| --- | --- | --- |
| `EMAIL_VERIFICATION_REQUIRED` | `False` | Hard-gate onboarding on email confirmation |
| `RATELIMIT_ENABLE` | `True` | Fixed-window throttling for sensitive actions |
| `CACHE_BACKEND` | `locmem` | `redis` / `memcached` for shared counters in production |
| `ANALYTICS_ENABLED` + `ANALYTICS_DOMAIN` | off | Cookie-less Plausible analytics |
| `CONTACT_EMAIL` | from email | Inbox for the public contact form |
| `MATCH_EMAILS_ENABLED` | `True` | Whether the "it's mutual" alert is emailed |

## Documentation

- `docs/architecture.md` — apps, models, flows, and invariants.
- `docs/privacy-and-matching.md` — privacy guarantees, matching, verification.
- `docs/seo-checklist.md` — what is indexable, structured data, share cards.
- `docs/growth-plan.md` — campus landing pages, invite links, blog, FAQ.
- `docs/deployment.md` — Postgres, WhiteNoise, Redis, security, ops.