from django.urls import path, include
from . import views

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    # Both of these also arrive with the set below, which is why they are
    # written out first: the earlier pattern is the one that answers, and these
    # two carry a limit the built-in ones do not.
    path("password_reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path("", include("django.contrib.auth.urls")),
    path("", views.home, name="home"),
    path("feed/updates/", views.feed_updates, name="feed_updates"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("edit/", views.edit, name="edit"),
    # One view behind both: the owner's page is the same page without a name.
    path("me/", views.profile, name="my_profile"),
    path("me/photo/", views.profile_photo_update, name="profile_photo"),
    path("me/photo/delete/", views.profile_photo_delete, name="profile_photo_delete"),
    path("users/", views.user_list, name="user_list"),
    path("users/<username>/", views.profile, name="user_detail"),
]
