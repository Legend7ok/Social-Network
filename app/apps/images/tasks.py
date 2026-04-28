import os
from urllib.parse import urlparse

import requests
from celery import shared_task
from django.core.files.base import ContentFile
from django.utils.text import slugify

from .models import Image


@shared_task
def download_image(image_id, url):
    try:
        image = Image.objects.get(id=image_id)
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        extension = os.path.splitext(urlparse(url).path)[1].lstrip(".").lower()
        name = f"{slugify(image.title)}.{extension}"
        image.image.save(name, ContentFile(response.content), save=True)
    except Exception:
        pass
