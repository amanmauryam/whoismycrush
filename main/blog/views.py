from __future__ import annotations

from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from config import seo
from config.ratelimit import ratelimit

from .models import Category, Post
from .utils import add_heading_ids, extract_toc
from .validators import validate_cover_image

HOME = ("Home", "/")


def _tips():
    return ("Pro Tips", reverse("blog:post_list"))


class PostListView(ListView):
    model = Post
    template_name = "blog/post_list.html"
    context_object_name = "posts"
    paginate_by = 9

    def get_queryset(self):
        self.search_query = self.request.GET.get("q", "").strip()[:80]
        self.category_slug = self.kwargs.get("category", "")
        self.active_category = (
            get_object_or_404(Category, slug=self.category_slug)
            if self.category_slug
            else None
        )

        queryset = Post.published.select_related("category")
        if self.active_category:
            queryset = queryset.filter(category=self.active_category)
        if self.search_query:
            queryset = queryset.filter(
                Q(title__icontains=self.search_query)
                | Q(excerpt__icontains=self.search_query)
                | Q(body__icontains=self.search_query)
                | Q(category__name__icontains=self.search_query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page_obj = context.get("page_obj")
        first_page = not page_obj or page_obj.number == 1
        searching = bool(self.search_query)

        lead = None
        lead_is_featured = False
        featured_posts: list[Post] = []

        if first_page and not searching:
            featured = list(self.get_queryset().filter(is_featured=True)[:3])
            if featured:
                lead = featured[0]
                lead_is_featured = True
                featured_posts = featured[1:]
            elif context["posts"]:
                lead = context["posts"][0]

        if lead:
            excluded = {lead.pk, *(item.pk for item in featured_posts)}
            context["posts"] = [post for post in context["posts"] if post.pk not in excluded]

        if searching:
            context["posts"] = list(context["posts"])

        context.update(
            {
                "active_category": self.active_category,
                "search_query": self.search_query,
                "lead": lead,
                "lead_is_featured": lead_is_featured,
                "featured_posts": featured_posts,
                "categories": self._categories(),
                "total_published": (
                    self.get_queryset().count()
                    if self.active_category
                    else Post.published.count()
                ),
                "querystring": self._querystring(),
            }
        )
        context.update(self._seo_context(context, page_obj))
        return context

    def _categories(self):
        now = timezone.now()
        return Category.objects.annotate(
            published_count=Count(
                "posts",
                filter=Q(
                    posts__is_published=True,
                    posts__published_at__lte=now,
                ),
                distinct=True,
            )
        ).order_by("order", "name")

    def _querystring(self) -> str:
        params = self.request.GET.copy()
        params.pop("page", None)
        return params.urlencode()

    def _seo_context(self, context, page_obj) -> dict:
        category = self.active_category
        path = reverse(
            "blog:category", kwargs={"category": category.slug}
        ) if category else reverse("blog:post_list")
        if page_obj and page_obj.number > 1 and not self.search_query:
            path = f"{path}?page={page_obj.number}"

        if self.search_query:
            title = f'Search: "{self.search_query}"'
            description = (
                f"Pro Tips matching “{self.search_query}” — guides for campus, "
                "privacy, matching and the WhoIsMyCrush app."
            )
            can_index = False
            breadcrumbs = [HOME, _tips(), (title, None)]
        elif category:
            title = f"{category.name} · Pro Tips"
            description = category.description or (
                f"{category.name} guides and tips from WhoIsMyCrush."
            )
            can_index = True
            breadcrumbs = [HOME, _tips(), (category.name, category.get_absolute_url())]
        else:
            title = "Pro Tips"
            description = (
                "Field notes from WhoIsMyCrush: account guides, feature "
                "tutorials, privacy tips, troubleshooting and small website "
                "tricks for your campus."
            )
            can_index = True
            breadcrumbs = [HOME, _tips()]

        return {
            "page_title": title,
            "meta_description": description,
            "canonical_path": path,
            "can_index": can_index,
            "og_type": "website",
            "structured_data": [seo.breadcrumb(breadcrumbs)],
        }


class PostDetailView(DetailView):
    model = Post
    template_name = "blog/post_detail.html"
    context_object_name = "post"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return Post.published.select_related("category")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.object
        body_html = add_heading_ids(post.body_html)
        toc = extract_toc(body_html)

        related = list(
            Post.published.select_related("category")
            .filter(category=post.category)
            .exclude(pk=post.pk)[:3]
        )
        if len(related) < 3:
            filler = (
                Post.published.select_related("category")
                .exclude(pk=post.pk)
                .exclude(pk__in=[item.pk for item in related])[: 3 - len(related)]
            )
            related.extend(filler)

        newer = (
            Post.published.filter(published_at__gt=post.published_at)
            .order_by("published_at")
            .first()
        )
        older = (
            Post.published.filter(published_at__lt=post.published_at)
            .order_by("-published_at")
            .first()
        )

        breadcrumbs = [HOME, _tips()]
        if post.category:
            breadcrumbs.append(
                (post.category.name, post.category.get_absolute_url())
            )
        breadcrumbs.append((post.title, post.canonical))

        context.update(
            {
                "body_html": body_html,
                "toc": toc,
                "related": related,
                "newer_post": newer,
                "older_post": older,
                "page_title": post.meta_title,
                "meta_description": post.description,
                "canonical_path": post.canonical,
                "og_type": "article",
                "og_image_path": post.image_url,
                "structured_data": [
                    seo.breadcrumb(breadcrumbs),
                    seo.article(post),
                ],
            }
        )
        return context


@require_POST
@ratelimit(key="user", rate="60/h")
def editor_image_upload(request):
    """Staff-only CKEditor 5 upload endpoint with the same strict validation."""

    if not request.user.is_staff:
        return JsonResponse(
            {"error": {"message": "You do not have permission to upload files."}},
            status=403,
        )

    upload = request.FILES.get("upload")
    if not upload:
        return JsonResponse(
            {"error": {"message": "No image was received."}},
            status=400,
        )

    try:
        validate_cover_image(upload)
    except ValidationError as exc:
        return JsonResponse(
            {"error": {"message": " ".join(exc.messages)}},
            status=400,
        )

    safe_name = Path(upload.name).name or "image"
    target = f"blog/inline/{timezone.now():%Y/%m}/{safe_name}"
    saved_name = default_storage.save(target, upload)
    return JsonResponse({"url": default_storage.url(saved_name)})


def legacy_post_redirect(request, slug):
    """Keep old /blog/<slug>/ links working after the Pro Tips move."""

    post = get_object_or_404(Post.published, slug=slug)
    return redirect(post, permanent=True)
