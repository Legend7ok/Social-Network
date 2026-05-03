from django.urls import path
from .views import ImageLikeView

urlpatterns = [
    path("<int:pk>/like/", ImageLikeView.as_view(), name="image-like"),
]
