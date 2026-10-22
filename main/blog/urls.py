from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.PostListView.as_view(), name="post_list"),
    path(
        "category/<slug:category>/",
        views.PostListView.as_view(),
        name="category",
    ),
    path(
        "editor/image-upload/",
        views.editor_image_upload,
        name="editor_image_upload",
    ),
    path("<slug:slug>/", views.PostDetailView.as_view(), name="post_detail"),
]
