"""Tests for the public marketing surface, JSON-LD, sanitizer and throttling."""

from __future__ import annotations

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from config.content import FAQ_GROUPS, faq_pairs
from config.ratelimit import parse_rate, ratelimit
from config.sanitize import sanitize_html

from .forms import ContactForm

CORE_PAGES = [
    "core:about",
    "core:how_it_works",
    "core:secret_crush",
    "core:mutual_crush",
    "core:college_crush",
    "core:faq",
    "core:safety",
    "core:privacy_policy",
    "core:terms",
    "core:contact",
]


class SanitizeHtmlTests(TestCase):
    def test_script_tag_and_content_removed(self):
        result = sanitize_html("<p>hi</p><script>alert(1)</script>")
        self.assertNotIn("<script", result)
        self.assertNotIn("alert", result)
        self.assertIn("<p>hi</p>", result)

    def test_event_handler_attributes_stripped(self):
        result = sanitize_html('<img src="/x.png" onerror="steal()">')
        self.assertNotIn("onerror", result)
        self.assertIn('src="/x.png"', result)

    def test_javascript_urls_dropped(self):
        result = sanitize_html('<a href="javascript:alert(1)">x</a>')
        self.assertNotIn("javascript:", result)
        self.assertIn("<a", result)

    def test_safe_links_get_rel(self):
        result = sanitize_html('<a href="https://example.com">e</a>')
        self.assertIn('rel="nofollow noopener noreferrer"', result)

    def test_unbalanced_tags_are_closed(self):
        result = sanitize_html("<p>oops")
        self.assertTrue(result.endswith("</p>"))

    def test_text_is_escaped(self):
        result = sanitize_html("<p>5 < 6 & 7 > 2</p>")
        self.assertIn("5 &lt; 6 &amp; 7 &gt; 2", result)


class MarketingPageTests(TestCase):
    def test_every_core_page_renders(self):
        for name in CORE_PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)

    def test_pages_emit_breadcrumb_structured_data(self):
        response = self.client.get(reverse("core:about"))
        self.assertContains(response, "BreadcrumbList")

    def test_faq_page_emits_faqpage_markup(self):
        response = self.client.get(reverse("core:faq"))
        self.assertContains(response, "FAQPage")
        self.assertContains(response, FAQ_GROUPS[0]["title"])

    def test_blog_route_is_wired(self):
        self.assertEqual(self.client.get(reverse("blog:post_list")).status_code, 200)

    def test_faq_pairs_flattens_groups(self):
        pairs = faq_pairs()
        expected = sum(len(group["items"]) for group in FAQ_GROUPS)
        self.assertEqual(len(pairs), expected)


class StructuredDataTests(TestCase):
    def test_site_jsonld_is_embedded(self):
        response = self.client.get(reverse("core:about"))
        html = response.content.decode()
        self.assertIn("application/ld+json", html)
        self.assertIn('"@type":"Organization"', html)
        self.assertIn('"@type":"WebSite"', html)


class ContactFormTests(TestCase):
    def _payload(self, **overrides):
        data = {
            "name": "Sam",
            "email": "sam@example.edu",
            "topic": "general",
            "message": "Hello there",
        }
        data.update(overrides)
        return data

    def test_valid_submission_sends_mail(self):
        response = self.client.post(reverse("core:contact"), self._payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Hello there", mail.outbox[0].body)

    def test_honeypot_blocks_bots(self):
        response = self.client.post(
            reverse("core:contact"), self._payload(website="http://spam.example")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(ContactForm(self._payload(website="x")).is_valid())

    def test_message_is_trimmed(self):
        form = ContactForm(self._payload(message="  spaced  "))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["message"], "spaced")


class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_parse_rate(self):
        self.assertEqual(parse_rate("5/m"), (5, 60))
        self.assertEqual(parse_rate("10/h"), (10, 3600))
        self.assertEqual(parse_rate("garbage"), (1, 60))

    @override_settings(RATELIMIT_ENABLE=True)
    def test_contact_post_is_throttled(self):
        payload = {
            "name": "Sam",
            "email": "sam@example.edu",
            "topic": "general",
            "message": "hi",
        }
        statuses = [
            self.client.post(reverse("core:contact"), payload).status_code
            for _ in range(6)
        ]
        self.assertEqual(statuses[:5], [302] * 5)
        self.assertEqual(statuses[5], 429)

    @override_settings(RATELIMIT_ENABLE=False)
    def test_limit_can_be_disabled(self):
        for _ in range(20):
            self.assertEqual(
                self.client.post(
                    reverse("core:contact"),
                    {"name": "S", "email": "s@e.edu", "topic": "general", "message": "hi"},
                ).status_code,
                302,
            )


class _FakeRequest:
    def __init__(self, method="POST", ip="1.2.3.4"):
        self.method = method
        self.META = {"REMOTE_ADDR": ip}
        self.user = type("U", (), {"is_authenticated": False, "pk": None})()


class RateLimitDecoratorTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @override_settings(RATELIMIT_ENABLE=True)
    def test_decorator_blocks_after_limit(self):
        calls = {"n": 0}

        @ratelimit(key="ip", rate="2/m")
        def view(request):
            calls["n"] += 1
            from django.http import HttpResponse

            return HttpResponse("ok")

        req = _FakeRequest()
        self.assertEqual(view(req).status_code, 200)
        self.assertEqual(view(req).status_code, 200)
        self.assertEqual(view(req).status_code, 429)
        self.assertEqual(calls["n"], 2)

    @override_settings(RATELIMIT_ENABLE=False)
    def test_decorator_is_inert_when_disabled(self):
        @ratelimit(key="ip", rate="1/m")
        def view(request):
            from django.http import HttpResponse

            return HttpResponse("ok")

        for _ in range(5):
            self.assertEqual(view(_FakeRequest()).status_code, 200)
