from django.conf import settings


def site_url(request):
    return {"site_url": settings.SITE_URL}


def thumbnails(request):
    return {"THUMBS": settings.THUMBNAILS}
