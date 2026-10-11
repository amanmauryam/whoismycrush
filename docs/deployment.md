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
DEFAULT_FROM_EMAIL=no-reply@whoismycrush.com
CONTACT_EMAIL=contact@whoismycrush.com
CACHE_BACKEND=redis
REDIS_URL=redis://…/1
RATELIMIT_ENABLE=True
ANALYTICS_ENABLED=False            # set both only when using Plausible
ANALYTICS_DOMAIN=
```

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

Production workers must be HTTP/WSGI behind the proxy; create the admin and
the verifier user with `campus.verify_potentialmatch` permission granted.

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
- [ ] Email is on a real SMTP/transactional provider (`EMAIL_BACKEND`).
- [ ] Redis reachable, `CACHES` pointed at it, `RATELIMIT_ENABLE=True`.
- [ ] `seed_posts` run so the blog isn't an empty directory index.
- [ ] Backups for Postgres and `MEDIA_ROOT`.
- [ ] Monitoring on: 5xx rate, match-verification queue length (`/staff/`),
      429 codes, `Reports` backlog.
- [ ] `robots.txt` and `sitemap.xml` return 200 with `SITE_URL` correct.

## Not in scope

Payment gateways (roses are dormant), an external analytics SPA tag, and
multi-tenancy — the product is intentionally single-tenant, one college world
at a time.