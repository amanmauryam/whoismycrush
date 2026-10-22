"""Tests for the blog: publishing rules, sanitized bodies, views and sitemap."""

from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import Category, Post
from .validators import validate_cover_image


def make_post(**overrides):
    defaults = {
        "title": "A secret crush story",
        "excerpt": "Something short.",
        "body": "<p>Body</p>",
        "is_published": True,
    }
    defaults.update(overrides)
    return Post.objects.create(**defaults)


class CategoryModelTests(TestCase):
    def test_slug_is_generated_from_name(self):
        category = Category.objects.create(name="Privacy & Safety")
        self.assertEqual(category.slug, "privacy-safety")

    def test_category_url_points_at_pro_tips_archive(self):
        category = Category.objects.create(name="Troubleshooting")
        self.assertEqual(
            category.get_absolute_url(),
            f"/pro-tips/category/{category.slug}/",
        )

    def test_post_inherits_category_accent(self):
        category = Category.objects.create(name="Privacy", accent="green")
        post = make_post(category=category)
        self.assertEqual(post.accent, "green")


class PostModelTests(TestCase):
    def test_slug_is_generated_from_title(self):
        post = make_post(title="Mutual Crush Basics")
        self.assertEqual(post.slug, "mutual-crush-basics")

    def test_duplicate_titles_get_unique_slugs(self):
        first = make_post(title="Same Title")
        second = make_post(title="Same Title")
        self.assertNotEqual(first.slug, second.slug)
        self.assertTrue(second.slug.startswith("same-title"))

    def test_publishing_stamps_published_at(self):
        post = make_post()
        self.assertIsNotNone(post.published_at)

    def test_body_html_is_sanitized(self):
        post = make_post(body="<p>ok</p><script>bad()</script>")
        self.assertNotIn("script", post.body_html)
        self.assertIn("<p>ok</p>", post.body_html)

    def test_reading_minutes_is_at_least_one(self):
        self.assertEqual(make_post(body="tiny").reading_minutes, 1)

    def test_word_count_ignores_html_markup(self):
        post = make_post(body="<p>One <strong>two</strong> three</p>")
        self.assertEqual(post.word_count, 3)

    def test_reading_minutes_tracks_longer_articles(self):
        post = make_post(body=" ".join(["word"] * 660))
        self.assertEqual(post.reading_minutes, 3)

    def test_blank_target_links_get_rel_attributes(self):
        post = make_post(
            body='<p><a href="https://example.com" target="_blank">link</a></p>'
        )
        self.assertIn('target="_blank"', post.body_html)
        self.assertIn('rel="nofollow noopener noreferrer"', post.body_html)

    def test_javascript_links_are_removed(self):
        post = make_post(body='<p><a href="javascript:alert(1)">bad</a></p>')
        self.assertNotIn("javascript:", post.body_html)
        self.assertIn("<a>bad</a>", post.body_html)

    def test_image_url_falls_back_to_static(self):
        self.assertEqual(make_post().image_url, "/static/img/og-default.png")


class PublishedManagerTests(TestCase):
    def test_drafts_are_hidden(self):
        make_post(title="Live", is_published=True)
        make_post(title="Draft", is_published=False)
        titles = list(Post.published.values_list("title", flat=True))
        self.assertEqual(titles, ["Live"])

    def test_future_posts_are_hidden(self):
        make_post(title="Now")
        make_post(
            title="Later",
            published_at=timezone.now() + timedelta(days=7),
        )
        titles = list(Post.published.values_list("title", flat=True))
        self.assertEqual(titles, ["Now"])


class BlogViewTests(TestCase):
    def test_list_shows_only_published(self):
        make_post(title="Visible Post")
        make_post(title="Hidden Draft", is_published=False)
        response = self.client.get(reverse("blog:post_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible Post")
        self.assertNotContains(response, "Hidden Draft")

    def test_featured_post_becomes_the_lead(self):
        category = Category.objects.create(name="Secret tips", accent="yellow")
        featured = make_post(
            title="Featured tip",
            category=category,
            is_featured=True,
        )
        make_post(title="Regular tip", category=category)
        response = self.client.get(reverse("blog:post_list"))
        self.assertEqual(response.context["lead"], featured)
        self.assertTrue(response.context["lead_is_featured"])

    def test_category_archive_filters_posts(self):
        privacy = Category.objects.create(name="Privacy", accent="green")
        other = Category.objects.create(name="Tutorials", accent="pink")
        make_post(title="Private list advice", category=privacy)
        make_post(title="Picker walkthrough", category=other)
        response = self.client.get(privacy.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_category"], privacy)
        self.assertContains(response, "Private list advice")
        self.assertNotContains(response, "Picker walkthrough")

    def test_search_filters_posts_and_is_noindex(self):
        make_post(title="How to stay private", body="<p>Lock it down.</p>")
        make_post(title="Campus picker guide", body="<p>Find your college.</p>")
        response = self.client.get(reverse("blog:post_list"), {"q": "private"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["search_query"], "private")
        self.assertFalse(response.context["can_index"])
        self.assertContains(response, "How to stay private")
        self.assertNotContains(response, "Campus picker guide")

    def test_detail_renders_article_structured_data(self):
        post = make_post(title="Match Guide", body="<h2>Step one</h2>")
        response = self.client.get(post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BlogPosting")
        self.assertContains(response, "Step one")

    def test_detail_builds_safe_table_of_contents(self):
        post = make_post(
            title="TOC guide",
            body="<h2>Step one</h2><p>Text.</p><h3>Details</h3>",
        )
        response = self.client.get(post.get_absolute_url())
        self.assertEqual(
            [item["id"] for item in response.context["toc"]],
            ["step-one", "details"],
        )
        self.assertIn('id="step-one"', response.context["body_html"])

    def test_draft_detail_is_404(self):
        post = make_post(title="Draft", is_published=False)
        response = self.client.get(post.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_legacy_blog_urls_redirect_to_pro_tips(self):
        post = make_post(title="Old link")
        list_response = self.client.get("/blog/")
        self.assertEqual(list_response.status_code, 301)
        self.assertEqual(list_response["Location"], "/pro-tips/")
        detail_response = self.client.get(f"/blog/{post.slug}/")
        self.assertEqual(detail_response.status_code, 301)
        self.assertEqual(detail_response["Location"], post.get_absolute_url())

    def test_sitemap_includes_published_posts_and_categories(self):
        category = Category.objects.create(name="Privacy")
        post = make_post(title="Indexed", category=category)
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, post.get_absolute_url())
        self.assertContains(response, category.get_absolute_url())


class EditorUploadTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.User = get_user_model()

    def staff_user(self):
        return self.User.objects.create_user(
            username="editor",
            password="test-pass-123",
            is_staff=True,
        )

    def image_file(self, name="image.png"):
        buffer = BytesIO()
        Image.new("RGB", (12, 12), "red").save(buffer, format="PNG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

    def test_non_staff_cannot_upload(self):
        user = self.User.objects.create_user(
            username="member",
            password="test-pass-123",
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("blog:editor_image_upload"),
            {"upload": self.image_file()},
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_upload_requires_an_image(self):
        self.client.force_login(self.staff_user())
        response = self.client.post(reverse("blog:editor_image_upload"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("No image", response.json()["error"]["message"])

    def test_staff_upload_rejects_non_image_files(self):
        self.client.force_login(self.staff_user())
        upload = SimpleUploadedFile(
            "notes.txt",
            b"not an image",
            content_type="text/plain",
        )
        response = self.client.post(
            reverse("blog:editor_image_upload"),
            {"upload": upload},
        )
        self.assertEqual(response.status_code, 400)

    def test_staff_upload_saves_valid_image(self):
        self.client.force_login(self.staff_user())
        response = self.client.post(
            reverse("blog:editor_image_upload"),
            {"upload": self.image_file()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("/media/blog/inline/", response.json()["url"])

    def test_validator_rejects_bad_extensions(self):
        with self.assertRaises(ValidationError):
            validate_cover_image(
                SimpleUploadedFile(
                    "cover.pdf",
                    b"%PDF-1.4",
                    content_type="application/pdf",
                )
            )


class SeedPostsCommandTests(TestCase):
    def test_seed_is_idempotent(self):
        call_command("seed_posts", verbosity=0)
        first = Post.objects.count()
        self.assertGreater(first, 0)
        call_command("seed_posts", verbosity=0)
        self.assertEqual(Post.objects.count(), first)

    def test_seeded_posts_are_published_and_visible(self):
        call_command("seed_posts", verbosity=0)
        self.assertTrue(Post.published.exists())
        response = self.client.get(reverse("blog:post_list"))
        self.assertEqual(response.status_code, 200)

    def test_seed_creates_categories_and_featured_posts(self):
        call_command("seed_posts", verbosity=0)
        self.assertEqual(Category.objects.count(), 6)
        self.assertFalse(Post.objects.filter(category__isnull=True).exists())
        self.assertEqual(Post.published.filter(is_featured=True).count(), 3)
