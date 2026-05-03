from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"
    ),
    path("images/", include("apps.images.api.urls")),
    path("users/", include("apps.account.api.urls")),
]
