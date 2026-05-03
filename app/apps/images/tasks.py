import os
from urllib.parse import urlparse

import requests
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.utils.text import slugify
from sorl.thumbnail import get_thumbnail

from .models import Image
from .services import get_image_ranking


@shared_task
def refresh_image_ranking_cache():
    image_ranking_ids = get_image_ranking()
    images_by_id = {
        image.id: image for image in Image.objects.filter(id__in=image_ranking_ids)
    }
    most_viewed = [images_by_id[id] for id in image_ranking_ids if id in images_by_id]
    cache.set(
        settings.IMAGE_RANKING_CACHE_KEY, most_viewed, settings.IMAGE_RANKING_CACHE_TTL
    )


@shared_task
def download_image(image_id, url):
    try:
        image = Image.objects.get(id=image_id)
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        extension = os.path.splitext(urlparse(url).path)[1].lstrip(".").lower()
        name = f"{slugify(image.title)}.{extension}"
        image.image.save(name, ContentFile(response.content), save=True)
        get_thumbnail(image.image, "300x300", crop="center")
        get_thumbnail(image.image, "300")
    except Exception:
        pass
