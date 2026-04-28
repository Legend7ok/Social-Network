from django.contrib import admin
from django.urls import path, include
from django.conf import settings

urlpatterns = [
    path("admin/", admin.site.urls),
    path("account/", include("apps.account.urls")),
    path("social-auth/", include("social_django.urls", namespace="social")),
    path("images/", include("apps.images.urls", namespace="images")),
]

if settings.DEBUG:
    import debug_toolbar
    from django.conf.urls.static import static

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
