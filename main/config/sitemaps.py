from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

# Only genuinely public, indexable pages. Campus names are never indexed:
# there is no public college directory (design.md 54).
STATIC_ROUTES = {
    "campus:landing": (1.0, "weekly"),
    "core:how_it_works": (0.8, "monthly"),
    "core:secret_crush": (0.7, "monthly"),
    "core:mutual_crush": (0.7, "monthly"),
    "core:college_crush": (0.7, "monthly"),
    "blog:post_list": (0.6, "weekly"),
    "core:faq": (0.6, "monthly"),
    "campus:campus_select": (0.7, "weekly"),
    "campus:invite": (0.4, "monthly"),
    "core:safety": (0.5, "yearly"),
    "core:about": (0.5, "yearly"),
    "core:privacy_policy": (0.4, "yearly"),
    "core:contact": (0.4, "yearly"),
    "core:terms": (0.3, "yearly"),
}


class StaticSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return list(STATIC_ROUTES)

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return STATIC_ROUTES[item][0]

    def changefreq(self, item):
        return STATIC_ROUTES[item][1]


def site_url() -> str:
    return (getattr(settings, "SITE_URL", "") or "http://127.0.0.1:8000").rstrip("/")


class AbsoluteUrlSitemap(StaticSitemap):
    """Same routes, but with correct canonical absolute URLs.

    Django's sitemap view builds "<protocol>://<domain><location>" and its
    default site domain is example.com, which would publish wrong canonical
    URLs. Overriding get_urls lets us emit the full loc ourselves.
    """

    def get_urls(self, page=None, protocol=None, domain=None, site=None):
        base = site_url()
        for item in self.items():
            yield {
                "location": f"{base}{reverse(item)}",
                "lastmod": None,
                "changefreq": self.changefreq(item),
                "priority": self.priority(item),
            }