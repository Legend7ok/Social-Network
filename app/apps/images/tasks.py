import logging
import os
from urllib.parse import urlparse

import requests
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.text import slugify
from sorl.thumbnail import get_thumbnail

from .models import Image

logger = logging.getLogger(__name__)


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
    response = requests.get(url, timeout=10, stream=True)
    response.raise_for_status()

    chunks = []
    size = 0
    for chunk in response.iter_content(chunk_size=8192):
        size += len(chunk)
        if size > settings.MAX_UPLOAD_SIZE:
            response.close()
            logger.warning(
                "download_image: %s exceeds MAX_UPLOAD_SIZE, discarding image %s",
                url,
                image_id,
            )
            image.delete()
            return
        chunks.append(chunk)

    extension = os.path.splitext(urlparse(url).path)[1].lstrip(".").lower()
    name = f"{slugify(image.title)}.{extension}"
    image.image.save(name, ContentFile(b"".join(chunks)), save=True)
    generate_image_thumbnails(image_id)
