from django.urls import path
from . import views

app_name = "images"

urlpatterns = [
    path("create/", views.image_create, name="create"),
    path(
        "bookmarklet_launcher.js",
        views.bookmarklet_launcher,
        name="bookmarklet_launcher",
    ),
    path("detail/<int:id>/<str:slug>/", views.image_detail, name="detail"),
    path("delete/<int:id>/", views.image_delete, name="delete"),
    path("", views.image_list, name="list"),
    path("ranking/", views.image_ranking, name="ranking"),
    path("status/<int:id>/", views.image_status, name="status"),
    path("upload/", views.image_upload, name="upload"),
]
