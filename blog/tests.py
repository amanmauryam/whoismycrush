"""Tests for the blog: publishing rules, sanitized bodies, views and sitemap."""

from __future__ import annotations

from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Post


def make_post(**overrides):
    defaults = {
        "title": "A secret crush story",
        "excerpt": "Something short.",
        "body": "<p>Body</p>",
        "is_published": True,
    }
    defaults.update(overrides)
    return Post.objects.create(**defaults)


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

    def test_detail_renders_article_structured_data(self):
        post = make_post(title="Match Guide", body="<h2>Step one</h2>")
        response = self.client.get(post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BlogPosting")
        self.assertContains(response, "Step one")

    def test_draft_detail_is_404(self):
        post = make_post(title="Draft", is_published=False)
        response = self.client.get(post.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_sitemap_includes_published_posts(self):
        post = make_post(title="Indexed")
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, post.get_absolute_url())


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
