"""Builders for accurate JSON-LD structured data.

Everything here describes content that is genuinely visible on the page. There
are deliberately no reviews, ratings, aggregate scores or FAQ blocks invented
for markup that the user cannot also read (requirements 12).
"""

from __future__ import annotations

from django.conf import settings
from django.urls import reverse


def _site_url() -> str:
    return (getattr(settings, "SITE_URL", "") or "http://127.0.0.1:8000").rstrip("/")


def _site_name() -> str:
    return getattr(settings, "SITE_NAME", "WhoIsMyCrush")


def organization() -> dict:
    base = _site_url()
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": base + "/#organization",
        "name": _site_name(),
        "url": base + "/",
        "logo": base + "/static/img/og-default.png",
        "description": (
            "A privacy-first college crush platform. Add up to three secret "
            "crushes and discover a mutual match only after verification."
        ),
    }


def website() -> dict:
    base = _site_url()
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": base + "/#website",
        "name": _site_name(),
        "url": base + "/",
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{base}{reverse('campus:campus_select')}?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }


def breadcrumb(items: list[tuple[str, str]]) -> dict:
    """``items`` is a list of ``(name, absolute_or_relative_url)``.

    The first item is always the home page; the final item has no URL because
    it is the current page.
    """
    base = _site_url()
    elements = []
    for position, (name, url) in enumerate(items, start=1):
        element = {
            "@type": "ListItem",
            "position": position,
            "name": name,
        }
        if url:
            element["item"] = url if url.startswith("http") else f"{base}{url}"
        elements.append(element)
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": elements}


def faq(pairs: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
            for question, answer in pairs
        ],
    }


def article(post) -> dict:
    base = _site_url()
    data = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post.title,
        "description": post.meta_description or post.excerpt,
        "datePublished": post.published_at.isoformat() if post.published_at else None,
        "dateModified": post.updated_at.isoformat() if post.updated_at else None,
        "author": {"@type": "Organization", "name": post.author_name or "WhoIsMyCrush"},
        "publisher": {"@type": "Organization", "name": "WhoIsMyCrush"},
        "mainEntityOfPage": f"{base}{post.get_absolute_url()}",
        "url": f"{base}{post.get_absolute_url()}",
        "articleSection": post.category.name if post.category else None,
        "wordCount": post.word_count,
        "timeRequired": f"PT{post.reading_minutes}M",
        "isAccessibleForFree": True,
    }
    if post.featured_image:
        image = post.image_url
        data["image"] = [image if image.startswith("http") else f"{base}{image}"]
    if post.updated_at:
        data["dateModified"] = post.updated_at.isoformat()
    return {k: v for k, v in data.items() if v is not None}
