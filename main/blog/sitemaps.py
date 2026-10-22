from django.contrib.sitemaps import Sitemap

from config.sitemaps import site_url

from .models import Category, Post


class BlogSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Post.published.all()

    def lastmod(self, item):
        return item.updated_at

    def get_urls(self, page=None, protocol=None, domain=None, site=None):
        base = site_url()
        for item in self.items():
            yield {
                "location": f"{base}{item.get_absolute_url()}",
                "lastmod": self.lastmod(item),
                "changefreq": self.changefreq,
                "priority": self.priority,
            }


class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return Category.objects.filter(posts__in=Post.published.all()).distinct()

    def get_urls(self, page=None, protocol=None, domain=None, site=None):
        base = site_url()
        for item in self.items():
            yield {
                "location": f"{base}{item.get_absolute_url()}",
                "lastmod": None,
                "changefreq": self.changefreq,
                "priority": self.priority,
            }
