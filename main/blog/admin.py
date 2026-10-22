from django.contrib import admin
from django.db.models import Count
from django.utils import timezone

from .models import Category, Post


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "accent", "post_count", "order")
    list_editable = ("order",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_post_count=Count("posts"))

    @admin.display(description="Posts", ordering="_post_count")
    def post_count(self, obj):
        return obj._post_count


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "is_featured",
        "is_published",
        "published_at",
        "author_name",
        "updated_at",
    )
    list_filter = ("is_published", "is_featured", "category", "author_name")
    search_fields = ("title", "excerpt", "body", "category__name")
    autocomplete_fields = ("category",)
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("category",)
    list_per_page = 25
    save_on_top = True
    actions = ("publish_posts", "unpublish_posts", "feature_posts", "unfeature_posts")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "slug",
                    "category",
                    "author_name",
                    "excerpt",
                )
            },
        ),
        (
            "Cover + placement",
            {
                "fields": ("featured_image", "is_featured"),
                "description": (
                    "Cover images are validated (JPG, PNG, WEBP or GIF, max 5 MB). "
                    "Featured tips appear at the top of Pro Tips."
                ),
            },
        ),
        (
            "Content",
            {
                "fields": ("body",),
                "description": (
                    "Use headings, lists, links, quotes, tables and inline images. "
                    "The public site sanitizes this HTML before rendering."
                ),
            },
        ),
        ("Publishing", {"fields": ("is_published", "published_at")}),
        ("SEO", {"fields": ("seo_title", "meta_description", "canonical_url")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.action(description="Publish selected posts")
    def publish_posts(self, request, queryset):
        for post in queryset:
            post.is_published = True
            if post.published_at is None:
                post.published_at = timezone.now()
            post.save(update_fields=("is_published", "published_at", "updated_at"))

    @admin.action(description="Unpublish selected posts")
    def unpublish_posts(self, request, queryset):
        queryset.update(is_published=False)

    @admin.action(description="Mark selected posts as featured")
    def feature_posts(self, request, queryset):
        queryset.update(is_featured=True)

    @admin.action(description="Remove selected posts from featured")
    def unfeature_posts(self, request, queryset):
        queryset.update(is_featured=False)
