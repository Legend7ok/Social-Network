from django.urls import path

from . import views

app_name = "comments"

urlpatterns = [
    path("add/<int:image_id>/", views.comment_create, name="create"),
    path("remove/<int:comment_id>/", views.comment_remove, name="remove"),
]
