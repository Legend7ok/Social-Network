import logging
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

logger = logging.getLogger(__name__)


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
def generate_image_thumbnails(image_id):
    try:
        image = Image.objects.get(id=image_id)
    except Image.DoesNotExist:
        logger.warning(
            "generate_image_thumbnails: image %s not found, skipping", image_id
        )
        return
    if not image.image:
        logger.warning(
            "generate_image_thumbnails: image %s has no file, skipping", image_id
        )
        return
    thumbs = settings.THUMBNAILS
    get_thumbnail(image.image, thumbs["content_card"], crop="center")
    get_thumbnail(image.image, thumbs["content_square"], crop="center")
    get_thumbnail(image.image, thumbs["detail_main"])


@shared_task(
    autoretry_for=(requests.RequestException,),
    max_retries=3,
    default_retry_delay=60,
    time_limit=300,
)
def download_image(image_id, url):
    try:
        image = Image.objects.get(id=image_id)
    except Image.DoesNotExist:
        logger.warning("download_image: image %s not found, skipping", image_id)
        return
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    extension = os.path.splitext(urlparse(url).path)[1].lstrip(".").lower()
    name = f"{slugify(image.title)}.{extension}"
    image.image.save(name, ContentFile(response.content), save=True)
    generate_image_thumbnails(image_id)
