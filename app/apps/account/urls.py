from django.urls import path, include
from . import views

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("", include("django.contrib.auth.urls")),
    path("", views.home, name="home"),
    path("feed/updates/", views.feed_updates, name="feed_updates"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("edit/", views.edit, name="edit"),
    # One view behind both: the owner's page is the same page without a name.
    path("me/", views.profile, name="my_profile"),
    path("me/photo/", views.profile_photo_update, name="profile_photo"),
    path("users/", views.user_list, name="user_list"),
    path("users/<username>/", views.profile, name="user_detail"),
]
