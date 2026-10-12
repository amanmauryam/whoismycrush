from __future__ import annotations

from django.urls import reverse
from django.views.generic import DetailView, ListView

from config import seo

from .models import Post

HOME = ("Home", "/")


class PostListView(ListView):
    model = Post
    template_name = "blog/post_list.html"
    context_object_name = "posts"
    paginate_by = 9

    def get_queryset(self):
        return Post.published.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Blog"
        context["meta_description"] = (
            "Guides and notes on secret crushes, college crushes, mutual "
            "matches and staying private."
        )
        context["canonical_path"] = reverse("blog:post_list")
        context["structured_data"] = [
            seo.breadcrumb([HOME, ("Blog", reverse("blog:post_list"))])
        ]
        return context


class PostDetailView(DetailView):
    model = Post
    template_name = "blog/post_detail.html"
    context_object_name = "post"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return Post.published.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.object
        context["page_title"] = post.meta_title
        context["meta_description"] = post.description
        context["canonical_path"] = post.canonical
        context["og_type"] = "article"
        context["og_image_path"] = post.image_url
        context["structured_data"] = [
            seo.breadcrumb(
                [HOME, ("Blog", reverse("blog:post_list")), (post.title, post.canonical)]
            ),
            seo.article(post),
        ]
        context["related"] = (
            Post.published.exclude(pk=post.pk)[:3]
        )
        return context
