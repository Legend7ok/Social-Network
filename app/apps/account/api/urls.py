from django.urls import path
from .views import UserFollowView

urlpatterns = [
    path("<int:pk>/follow/", UserFollowView.as_view(), name="user-follow"),
]
