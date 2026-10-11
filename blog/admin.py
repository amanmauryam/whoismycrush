from django.contrib import admin

from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "published_at", "author_name", "updated_at")
    list_filter = ("is_published", "author_name")
    search_fields = ("title", "excerpt", "body")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("title", "slug", "author_name", "featured_image")}),
        ("Content", {"fields": ("excerpt", "body")}),
        ("Publishing", {"fields": ("is_published", "published_at")}),
        ("SEO", {"fields": ("seo_title", "meta_description", "canonical_url")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
