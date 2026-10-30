# Deployment

## Stack

- Django 5.x, Python 3.12+, SQLite for dev / PostgreSQL for production.
- WhiteNoise serves the bundled static files; `collectstatic` must run in CI.
- No third-party throttling dependency: rate-limit counters live in `CACHES`.
- Django 5.2 `STORAGES` keys are used (`default` and `staticfiles`).

## Environment

Everything the app reads comes from `.env` (gitignored; there is no committed
template — keep this file backed up and out of the repo). The production-relevant
settings:

```
SECRET_KEY=…
DEBUG=False
ALLOWED_HOSTS=whoismycrush.com
DB_BACKEND=postgres
DB_NAME / DB_USER / DB_PASSWORD / DB_HOST / DB_PORT
SITE_URL=https://whoismycrush.com
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=…
EMAIL_HOST_PASSWORD=…            # an app password, not the account password
DEFAULT_FROM_EMAIL=no-reply@whoismycrush.com
CACHE_BACKEND=redis
REDIS_URL=redis://…/1
RATELIMIT_ENABLE=True
ANALYTICS_ENABLED=False            # set both only when using Plausible
ANALYTICS_DOMAIN=
# Identity resolution (safe defaults; only change with a reviewed rollout)
IDENTITY_AUTO_RESOLVE_ENABLED=True
IDENTITY_AUTO_RESOLVE_MIN_NAME_SIMILARITY=0.88
IDENTITY_NAME_CANDIDATE_MIN=0.70
IDENTITY_CANDIDATE_MIN_SCORE=50
IDENTITY_MAX_CANDIDATES=10
IDENTITY_FUZZY_SCAN_LIMIT=500
IDENTITY_REGISTRATION_SCAN_LIMIT=500
IDENTITY_REQUIRE_STUDENT_VERIFICATION_FOR_AUTO=False
# Matching policy (comma-separated field names; blank means no hard conflict)
MATCH_HARD_CONFLICT_FIELDS=course,year,section
MATCH_MIN_CONFIDENCE=40
MATCH_REQUIRE_ROLL_FOR_UNRESOLVED=True
IDENTITY_HARD_CONFLICT_FIELDS=course,year,section
# Notification outbox
NOTIFICATION_EMAIL_MAX_ATTEMPTS=5
# Verification-email outbox (registration returns before SMTP)
VERIFICATION_EMAIL_MAX_ATTEMPTS=5
VERIFICATION_EMAIL_TIMEOUT=45
VERIFICATION_EMAIL_STALE_SENDING_SECONDS=300
VERIFICATION_EMAIL_RETRY_AFTER_SECONDS=60
```

### Verification-email recovery timer

The registration/resend response only writes a durable `pending` row. A
best-effort daemon thread usually sends it immediately, but a process restart
can terminate that thread. Run the recovery command every minute so no email
stays pending and stale `sending` rows are reclaimed:

```cron
* * * * * cd /srv/whoismycrush && python manage.py process_verification_emails
```

The command logs outcomes without recipient addresses or verification links.
Failed rows are retried up to `VERIFICATION_EMAIL_MAX_ATTEMPTS`; a crash
between SMTP acceptance and the final database update can produce one
at-least-once duplicate, but the outbox row is never silently dropped.

`DEBUG=False` turns on HSTS, secure cookies and an SSL redirect that expects a
trusted proxy (`SECURE_PROXY_SSL_HEADER`). Terminate TLS at the proxy and make
sure it **overwrites** `X-Forwarded-For`, because
`config.ratelimit.client_ip` trusts its first segment.

## PostgreSQL vs SQLite

- SQLite is fine for a single worker and small local campus counts.
- Postgres (`docker-compose.yml`) is the deployment target: real
  concurrency, a shared Redis counter, and no "database is locked" surprises.

## Build & run

```powershell
# CI
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py seed_posts
python manage.py test

# app server (e.g. zappa/gunicorn-style command)
python manage.py runserver --insecure   # dev only
```

Production workers must be HTTP/WSGI behind the proxy; create the admin and the
review users with `campus.verify_potentialmatch` (match desk) and/or
`campus.review_identitycandidate` (identity desk) permissions granted.

### Identity-resolution migration (`campus.0004`)

Migration `0004_identitycandidate_identityresolutionaudit_and_more` adds
normalized names, optional crush rolls, resolved identity links, candidates,
audit rows, and `MutualMatch.notified_at`. It also backfills:

- normalized campus/profile/entry names and rolls;
- legacy exact-campus+roll proposals as resolved identities (ambiguous entries
  are left for review);
- existing mutual matches as already notified, so the new guard cannot send a
  duplicate alert.

Before deploying:

1. Take and verify a database backup.
2. Run `python manage.py migrate` in a staging copy and time it.
3. Check the identity queue at `/staff/identities/` after deploy; legacy entries
   without a reliable exact roll may legitimately appear there.
4. Grant the new review permission only to staff who need it.

Rollback of the migration is schema-only (`RunPython` reverse is a no-op), so
restore the pre-migration backup rather than reversing in production.

### Matching-audit migration (`campus.0005`)

Migration `0005_crushentry_original_payload_and_more` adds `STALE` proposals,
scoring versions/timestamps, first-submission snapshots (`original_payload`),
candidate status transitions in the identity audit, and the notification email
outbox. Its `RunPython` backfill:

- snapshots current values for existing entries (there is no older evidence to
  recover) and labels already-resolved entries `legacy`;
- marks existing notifications `email_status="skipped"` because email was
  handled synchronously before the outbox existed.

After deploy:

1. Run `python manage.py audit_matching` and review legacy counts.
2. Run `python manage.py reevaluate_matching --dry-run`, then without
   `--dry-run` during a quiet window if policy intentionally changed.
3. Monitor `python manage.py audit_matching` for failed emails, then retry with
   `python manage.py retry_notifications`.
4. Keep `MATCH_EMAILS_ENABLED=False` until SMTP is verified; in-app alerts are
   still written.

## Static + media

- `STATICFILES_DIRS = static/`, `STATIC_ROOT = staticfiles/` served by
  WhiteNoise with gzip/brotli + hashed filenames.
- `MEDIA_BACKEND=local` → on-disk `MEDIA_ROOT` (blog featured images).
  For `s3`, switch `STORAGES["default"]` to django-storages + boto3; the only
  upload today is blog images, so this is optional.
- Regenerate the OG image with `python scripts/make_og_image.py` whenever the
  brand card changes (it writes `static/img/og-default.png`).

## Rate limiting & cache topology

- Single-process: `CACHE_BACKEND=locmem` is fine.
- Multi-worker: set `CACHE_BACKEND=redis` (Redis) or `memcached`. Without a
  shared store, each worker keeps its own counters and the limits still hold —
  they just allow up to N× bursts. The limiter fails **open** on cache errors,
  so a broken cache never locks users out.

## Ops checklist

- [ ] `SECRET_KEY` unique, rotated, not in the repo.
- [ ] `DEBUG=False`, `ALLOWED_HOSTS` set.
- [ ] Proxy overwrites `X-Forwarded-For` and sends `X-Forwarded-Proto`.
- [ ] `collectstatic` ran; WhiteNoise configured; fonts/icons are the only
      external requests.
- [ ] Email is on a real SMTP/transactional provider (`EMAIL_BACKEND`), with
      `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD`
      all set.
- [ ] `python manage.py check_email --to <you>` passes — it proves the server
      accepts the credentials and that a message really leaves the box.
- [ ] `process_verification_emails` is scheduled every minute; after a test
      signup, the `EmailVerification` row reaches `sent` (or a logged `failed`).
- [ ] Redis reachable, `CACHES` pointed at it, `RATELIMIT_ENABLE=True`.
- [ ] `seed_posts` run so the blog isn't an empty directory index.
- [ ] Backups for Postgres and `MEDIA_ROOT`; restore drill completed.
- [ ] `python manage.py migrate` applied; identity backfill reviewed.
- [ ] Monitoring on: 5xx rate, match queue (`/staff/matches/`), identity queue
      (`/staff/identities/`), 429 codes, `Reports` backlog, duplicate
      notification counts.
- [ ] `robots.txt` and `sitemap.xml` return 200 with `SITE_URL` correct.

## Not in scope

Payment gateways (roses are dormant), an external analytics SPA tag, and
multi-tenancy — the product is intentionally single-tenant, one college world
at a time.