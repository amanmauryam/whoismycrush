from __future__ import annotations

import io
import math
import re
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field
from PIL import Image, ImageOps

from config.sanitize import sanitize_html

from .validators import validate_cover_image

_WORDS = re.compile(r"\S+")


def get_client_ip(request):
    """Extract the real user IP address handling reverse proxies/load balancers."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        # X-Forwarded-For can contain a comma-separated list of IPs
        ip = forwarded.split(",")[0].strip()
        if ip:
            return ip
    real_ip = request.META.get("HTTP_X_REAL_IP", "")
    if real_ip:
        ip = real_ip.strip()
        if ip:
            return ip
    return request.META.get("REMOTE_ADDR", "") or "unknown"


class Category(models.Model):
    """An editorial shelf for Pro Tips (privacy, tutorials, troubleshooting…)."""

    ACCENTS = (
        ("yellow", "Yellow"),
        ("pink", "Pink"),
        ("blue", "Blue"),
        ("green", "Green"),
        ("red", "Red"),
    )

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.TextField(
        max_length=240,
        blank=True,
        help_text="One line shown above the category archive.",
    )
    accent = models.CharField(max_length=10, choices=ACCENTS, default="yellow")
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def _unique_slug(self) -> str:
        base = slugify(self.name)[:80] or "category"
        candidate = base
        suffix = 2
        while Category.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def get_absolute_url(self) -> str:
        return reverse("blog:category", kwargs={"category": self.slug})


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
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="posts",
    )
    excerpt = models.TextField(
        max_length=320,
        help_text="One or two sentences shown on the index and in search results.",
    )
    body = CKEditor5Field(
        "body",
        config_name="extends",
        help_text="Rich text is sanitized before it is rendered on the public site.",
    )
    featured_image = models.ImageField(
        "cover image",
        upload_to="blog/covers/%Y/%m/",
        blank=True,
        null=True,
        validators=[validate_cover_image],
        help_text="Optional. JPG, PNG, WEBP or GIF, up to 5 MB.",
    )
    author_name = models.CharField(max_length=120, default="WhoIsMyCrush")
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Featured tips appear at the top of Pro Tips.",
    )

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
        self._convert_cover_to_webp()
        super().save(*args, **kwargs)

    def _convert_cover_to_webp(self):
        if not self.featured_image:
            return
        try:
            name = self.featured_image.name or ""
        except Exception:
            return
        if str(name).lower().endswith(".webp"):
            return
        try:
            file = self.featured_image.file
        except Exception:
            return
        try:
            file.seek(0)
        except Exception:
            pass
        try:
            with Image.open(file) as image:
                image = ImageOps.exif_transpose(image)
                if image.mode in ("RGBA", "LA", "P"):
                    background = Image.new("RGB", image.size, (255, 255, 255))
                    if image.mode == "P":
                        image = image.convert("RGBA")
                    if image.mode in ("RGBA", "LA"):
                        background.paste(image, mask=image.split()[-1])
                    else:
                        background.paste(image)
                    image = background
                elif image.mode != "RGB":
                    image = image.convert("RGB")
                buffer = io.BytesIO()
                image.save(buffer, format="WEBP", quality=85, method=6)
                buffer.seek(0)
        except Exception:
            try:
                file.seek(0)
            except Exception:
                pass
            return
        try:
            file.seek(0)
        except Exception:
            pass
        from django.core.files.storage import default_storage
        from django.utils import timezone

        now = timezone.now()
        stem = Path(str(name)).stem or "cover"
        filename = "%s.webp" % (slugify(stem) or "cover")
        new_name = "blog/covers/%04d/%02d/%s" % (now.year, now.month, filename)
        try:
            old = self.featured_image.name
            if old and old != new_name and default_storage.exists(old):
                default_storage.delete(old)
        except Exception:
            pass
        # Assign the saved file
        self.featured_image = self.featured_image.field.attr_class(
            self,
            self.featured_image.field,
            new_name,
        )
        self.featured_image.file = default_storage.open(new_name, "rb")
        # Actually save content
        saved_name = default_storage.save(new_name, ContentFile(buffer.getvalue()))
        self.featured_image.name = saved_name

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
    def word_count(self) -> int:
        return len(_WORDS.findall(re.sub(r"<[^>]+>", " ", self.body or "")))

    @property
    def reading_minutes(self) -> int:
        return max(1, math.ceil(self.word_count / 220))

    @property
    def accent(self) -> str:
        return self.category.accent if self.category else "yellow"

    @property
    def image_url(self) -> str:
        if self.featured_image:
            return self.featured_image.url
        return "/static/img/og-default.png"

    @property
    def total_unique_views(self) -> int:
        """Get total unique views count efficiently."""
        return self.views.count()


class PostView(models.Model):
    """Track unique blog post views per IP address."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="views")
    ip_address = models.GenericIPAddressField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("post", "ip_address")]
        indexes = [
            models.Index(fields=["post", "ip_address"]),
            models.Index(fields=["ip_address"]),
            models.Index(fields=["-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.post.title} - {self.ip_address}"


# Aliases for flexibility with different naming conventions
Blog = Post
BlogView = PostView
View = PostView
