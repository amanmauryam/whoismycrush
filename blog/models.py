from __future__ import annotations

import math
import re

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from config.sanitize import sanitize_html

_WORDS = re.compile(r"\S+")


class PublishedPostManager(models.Manager):
    """Only posts that are meant to be public, newest first."""

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(is_published=True, published_at__lte=timezone.now())
            .order_by("-published_at")
        )


class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    excerpt = models.TextField(
        max_length=320,
        help_text="One or two sentences shown on the index and in search results.",
    )
    body = models.TextField(
        help_text="A small safe subset of HTML is allowed; scripts are stripped.",
    )
    featured_image = models.ImageField(
        upload_to="blog/", blank=True, null=True,
        help_text="Optional; a sensible default image is used when omitted.",
    )
    author_name = models.CharField(max_length=120, default="WhoIsMyCrush")

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    seo_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=320, blank=True)
    canonical_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    published = PublishedPostManager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["-published_at"]),
            models.Index(fields=["is_published", "-published_at"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        if self.is_published and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def _unique_slug(self) -> str:
        base = slugify(self.title)[:200] or "post"
        candidate = base
        suffix = 2
        while Post.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def get_absolute_url(self) -> str:
        return reverse("blog:post_detail", kwargs={"slug": self.slug})

    @property
    def body_html(self) -> str:
        """Always sanitized at render time, never trusted from the database."""
        return sanitize_html(self.body)

    @property
    def meta_title(self) -> str:
        return self.seo_title or self.title

    @property
    def description(self) -> str:
        return self.meta_description or self.excerpt

    @property
    def canonical(self) -> str:
        return self.canonical_url or self.get_absolute_url()

    @property
    def reading_minutes(self) -> int:
        words = len(_WORDS.findall(re.sub(r"<[^>]+>", " ", self.body or "")))
        return max(1, math.ceil(words / 220))

    @property
    def image_url(self) -> str:
        if self.featured_image:
            return self.featured_image.url
        return "/static/img/og-default.png"
