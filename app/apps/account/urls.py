from django.contrib.auth import views as auth_views
from django.urls import path, include
from . import views

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(redirect_authenticated_user=True),
        name="login",
    ),
    path("", include("django.contrib.auth.urls")),
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("edit/", views.edit, name="edit"),
    path("me/", views.my_profile, name="my_profile"),
    path("me/photo/", views.profile_photo_update, name="profile_photo"),
    path("users/", views.user_list, name="user_list"),
    path("users/<username>/", views.user_detail, name="user_detail"),
]
