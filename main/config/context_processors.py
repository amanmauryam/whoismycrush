from django.conf import settings

from accounts.models import email_is_verified

from . import seo


def site(request):
    return {
        "SITE_NAME": getattr(settings, "SITE_NAME", "WhoIsMyCrush"),
        "SITE_TAGLINE": "You might be someone's crush too.",
        "SITE_URL": settings.SITE_URL,
        "SITE_AUTHOR": getattr(settings, "SITE_AUTHOR", "WhoIsMyCrush"),
        "SITE_KEYWORDS": getattr(settings, "SITE_KEYWORDS", ""),
        "GOOGLE_SITE_VERIFICATION": getattr(settings, "GOOGLE_SITE_VERIFICATION", ""),
        "BING_SITE_VERIFICATION": getattr(settings, "BING_SITE_VERIFICATION", ""),
        "YANDEX_SITE_VERIFICATION": getattr(settings, "YANDEX_SITE_VERIFICATION", ""),
        "email_verified": email_is_verified(getattr(request, "user", None)),
        "analytics_enabled": getattr(settings, "ANALYTICS_ENABLED", False),
        "analytics_domain": getattr(settings, "ANALYTICS_DOMAIN", ""),
    }


def structured_data(request):
    """Site-wide Organization + WebSite JSON-LD, emitted on every page."""
    return {"site_structured_data": [seo.organization(), seo.website()]}


def navigation(request):
    path = request.path

    unread_notifications = 0
    has_campus_id = False
    student = None
    if request.user.is_authenticated:
        student = getattr(request.user, "student", None)
        has_campus_id = student is not None
        if student is not None:
            unread_notifications = student.notifications.filter(is_read=False).count()

    return {
        "student": student,
        "has_campus_id": has_campus_id,
        "nav_home": path in ("", "/") or path.startswith("/about") or path.startswith("/how-it-works"),
        "nav_blog": path.startswith("/pro-tips") or path.startswith("/blog"),
        "nav_secret": path.startswith("/secret"),
        "nav_matches": path.startswith("/matches"),
        "nav_account": path.startswith("/campus-id") or path.startswith("/notifications"),
        "unread_notifications": unread_notifications,
    }