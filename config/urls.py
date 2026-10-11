from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import TemplateView

from blog.sitemaps import BlogSitemap
from config import views as core_views
from config.sitemaps import AbsoluteUrlSitemap

sitemaps = {
    "static": AbsoluteUrlSitemap,
    "blog": BlogSitemap,
}

core_patterns = (
    [
        path("about/", core_views.AboutView.as_view(), name="about"),
        path("how-it-works/", core_views.HowItWorksView.as_view(), name="how_it_works"),
        path("secret-crush/", core_views.SecretCrushView.as_view(), name="secret_crush"),
        path("mutual-crush/", core_views.MutualCrushView.as_view(), name="mutual_crush"),
        path("college-crush/", core_views.CollegeCrushView.as_view(), name="college_crush"),
        path("faq/", core_views.FAQView.as_view(), name="faq"),
        path("safety/", core_views.SafetyView.as_view(), name="safety"),
        path(
            "privacy-policy/",
            core_views.PrivacyPolicyView.as_view(),
            name="privacy_policy",
        ),
        path("terms/", core_views.TermsView.as_view(), name="terms"),
        path("contact/", core_views.ContactView.as_view(), name="contact"),
    ],
    "core",
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("campus.urls")),
    path("", include("accounts.urls")),
    path("blog/", include("blog.urls")),
    path("", include(core_patterns)),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
        name="robots",
    ),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "config.views.handler404"
handler500 = "config.views.handler500"
handler403 = "config.views.handler403"