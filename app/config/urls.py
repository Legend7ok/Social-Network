from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings

from core.views import handler429  # noqa: F401

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="home", permanent=False)),
    path("admin/", admin.site.urls),
    path("account/", include("apps.account.urls")),
    path("social-auth/", include("social_django.urls", namespace="social")),
    path("images/", include("apps.images.urls", namespace="images")),
    path("api/", include("config.api_urls")),
]

if settings.DEBUG:
    import debug_toolbar
    from django.conf.urls.static import static

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
