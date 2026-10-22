from pathlib import Path

from dotenv import load_dotenv
import os
import sys

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

#: True while ``manage.py test`` runs. Production security switches below are
#: skipped during tests so the suite behaves the same whatever ``.env`` says.
TESTING = "test" in sys.argv


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
if DEBUG:
    ALLOWED_HOSTS.extend(["testserver", ".localhost"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
    "django.contrib.sitemaps",
    "django_ckeditor_5",
    "accounts",
    "campus",
    "blog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.EmailVerificationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "libraries": {
                "seo": "config.templatetags.seo",
            },
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.site",
                "config.context_processors.structured_data",
                "config.context_processors.navigation",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DB_BACKEND = os.environ.get("DB_BACKEND", "sqlite").strip().lower()

if DB_BACKEND == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "whoismycrush"),
            "USER": os.environ.get("DB_USER", "whoismycrush"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "whoismycrush"),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTHENTICATION_BACKENDS = ["accounts.backends.EmailOrUsernameBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# CKEditor 5 (django-ckeditor-5 0.2.20)
#
# Verified against this project's Django 5.2.17 / Python 3.14.7 runtime:
# the package declares Django>=4.2 and Python>=3.8. It stores rich text in a
# normal TextField, is GPL-licensed, and its upload endpoint is replaced below
# with a staff-only view that applies the same image validation as covers.
# ---------------------------------------------------------------------------
CKEDITOR_5_CONFIGS = {
    "default": {
        "toolbar": ["heading", "|", "bold", "italic"],
    },
    "extends": {
        "toolbar": [
            {
                "name": "document",
                "items": [
                    "heading",
                    "|",
                    "bold",
                    "italic",
                    "underline",
                    "strikethrough",
                    "code",
                    "|",
                    "link",
                    "insertImage",
                    "uploadImage",
                    "insertTable",
                    "blockQuote",
                    "horizontalLine",
                ],
            },
            {
                "name": "lists",
                "items": [
                    "bulletedList",
                    "numberedList",
                    "|",
                    "outdent",
                    "indent",
                ],
            },
            {
                "name": "tools",
                "items": [
                    "findAndReplace",
                    "specialCharacters",
                    "|",
                    "removeFormat",
                    "|",
                    "undo",
                    "redo",
                ],
            },
        ],
        "heading": {
            "options": [
                {"model": "paragraph", "title": "Paragraph"},
                {
                    "model": "heading1",
                    "view": "h2",
                    "title": "Heading 2",
                    "class": "ck-heading_heading2",
                },
                {
                    "model": "heading2",
                    "view": "h3",
                    "title": "Heading 3",
                    "class": "ck-heading_heading3",
                },
                {
                    "model": "heading3",
                    "view": "h4",
                    "title": "Heading 4",
                    "class": "ck-heading_heading4",
                },
            ]
        },
        "image": {
            "styles": ["inline", "block", "side"],
            "toolbar": [
                "imageStyle:inline",
                "imageStyle:block",
                "imageStyle:side",
                "|",
                "toggleImageCaption",
                "imageTextAlternative",
                "|",
                "linkImage",
            ],
        },
        "table": {
            "contentToolbar": [
                "tableColumn",
                "tableRow",
                "mergeTableCells",
                "tableProperties",
                "tableCellProperties",
            ]
        },
        "list": {
            "properties": {
                "styles": ["lower-roman", "upper-roman", "lower-latin", "upper-latin"],
                "startIndex": True,
                "reversed": True,
            }
        },
        "link": {"addTargetToExternalLinks": True},
        "wordCount": {"displayWords": True, "displayCharacters": False},
    },
}

CKEDITOR_5_FILE_UPLOAD_PERMISSION = "staff"
CKEDITOR_5_ALLOW_ALL_FILE_TYPES = False
CKEDITOR_5_MAX_FILE_SIZE = 5  # MB
CKEDITOR_5_UPLOAD_FILE_TYPES = ["jpg", "jpeg", "png", "webp", "gif"]
CK_EDITOR_5_UPLOAD_FILE_VIEW_NAME = "blog:editor_image_upload"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SITE_ID = 1

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "campus:dashboard"
LOGOUT_REDIRECT_URL = "campus:landing"

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "SAMEORIGIN"


if not DEBUG and not TESTING:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0

DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024

# Fixed-window throttling for sensitive actions (config.ratelimit). Off during
# tests so the process-local cache cannot leak state between cases.
RATELIMIT_ENABLE = env_bool("RATELIMIT_ENABLE", not TESTING)

# Where the rate-limit counters live. A single process can use local memory;
# multi-worker production should point this at Redis or Memcached (see
# docs/deployment.md) so every worker shares one counter.
CACHE_BACKEND = os.environ.get("CACHE_BACKEND", "locmem").strip().lower()
if CACHE_BACKEND == "redis":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1"),
        }
    }
elif CACHE_BACKEND == "memcached":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
            "LOCATION": os.environ.get("MEMCACHED_URL", "127.0.0.1:11211"),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "whoismycrush-ratelimit",
        }
    }

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
# SMTP connection details. These have to be wired up explicitly: Django's
# defaults are localhost:25 with no credentials, so leaving them unset means
# every mail silently tries (and fails) to talk to a mail server on this
# machine. See config/mail.py for why a failure must never stay silent.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 25)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    EMAIL_USE_SSL = False
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 10)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@whoismycrush.local")
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", DEFAULT_FROM_EMAIL)

SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000").rstrip("/")

# Privacy-friendly, cookie-less analytics. Off unless explicitly enabled and a
# domain is set; no crush data is ever sent (see docs/privacy-and-matching.md).
ANALYTICS_ENABLED = env_bool("ANALYTICS_ENABLED", False)
ANALYTICS_DOMAIN = os.environ.get("ANALYTICS_DOMAIN", "")

MATCH_EMAILS_ENABLED = env_bool("MATCH_EMAILS_ENABLED", True)
MINIMUM_AGE = env_int("MINIMUM_AGE", 18)

# Email verification is on (links are emailed) but not blocking by default.
# Set EMAIL_VERIFICATION_REQUIRED=True to force confirmation before the rest of
# the product is reachable (accounts/middleware.py).
EMAIL_VERIFICATION_REQUIRED = env_bool("EMAIL_VERIFICATION_REQUIRED", False)
VERIFICATION_RESEND_COOLDOWN_SECONDS = env_int("VERIFICATION_RESEND_COOLDOWN_SECONDS", 60)

MESSAGE_STORAGE = "django.contrib.messages.storage.fallback.FallbackStorage"

# Logging. Django's default config only wires up the "django" namespace, so a
# failure in our own code would fall through to the root logger and disappear.
# Mail delivery failures in particular must be visible: they used to be
# swallowed entirely, which made a misconfigured SMTP server look exactly like
# a successful signup.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },
    "formatters": {
        "simple": {"fmt": "[{levelname}] {name}: {message}", "style": "{"},
        "django.server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[{server_time}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "django.server": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "django.server",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "django.server", "mail_admins"],
            "level": "INFO",
        },
        "django.server": {
            "handlers": ["django.server"],
            "level": "INFO",
            "propagate": False,
        },
        "config": {
            "handlers": ["console", "mail_admins"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
