import logging
import os
from urllib.parse import urlparse

import requests
from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db.models import F
from sorl.thumbnail import delete as delete_thumbnails
from sorl.thumbnail import get_thumbnail

from apps.actions.models import Action

from .models import Image
from .services import (
    clear_view_deltas,
    forget_image_views,
    get_dirty_image_ids,
    read_view_deltas,
)

logger = logging.getLogger(__name__)

FLUSH_BATCH_SIZE = 500


@shared_task
def flush_image_views():
    """
    Move buffered view counts from Redis into Image.total_views.

    The database is written first and Redis is only drained afterwards: a crash
    in between replays a batch on the next run, which is far better than the
    reverse order, where it would silently drop the views instead.
    """
    image_ids = get_dirty_image_ids()
    flushed = 0

    for start in range(0, len(image_ids), FLUSH_BATCH_SIZE):
        batch = image_ids[start : start + FLUSH_BATCH_SIZE]
        deltas = read_view_deltas(batch)
        pending = {image_id: delta for image_id, delta in deltas.items() if delta > 0}

        if pending:
            images = list(Image.objects.filter(id__in=pending).only("id"))
            for image in images:
                image.total_views = F("total_views") + pending[image.id]
            Image.objects.bulk_update(images, ["total_views"])
            flushed += len(images)

        # Deleted images and drained counters are cleared too, so their ids do
        # not linger in the dirty set forever.
        clear_view_deltas(deltas)

    if flushed:
        logger.info("flush_image_views: flushed views for %s images", flushed)
    return flushed


@shared_task(autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def delete_image_artifacts(image_id, file_name):
    """
    Clean up everything a deleted image leaves behind.

    Django does not remove files when a row goes away, the activity feed points
    at images through a generic relation without a foreign key, and the view
    counters live outside the database — so all three are dropped here. Every
    step is safe to repeat, which is what makes retrying the task harmless.
    """
    forget_image_views(image_id)

    Action.objects.filter(
        target_ct=ContentType.objects.get_for_model(Image),
        target_id=image_id,
    ).delete()

    if file_name:
        # Removes the stored file together with its thumbnails and the key
        # store entries pointing at them.
        delete_thumbnails(file_name)

    logger.info("delete_image_artifacts: cleaned up after image %s", image_id)


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
    # image.slug, not the raw title: a title without letters slugifies to an
    # empty string and would store a nameless ".jpg".
    name = f"{image.slug}.{extension}"
    image.image.save(name, ContentFile(b"".join(chunks)), save=False)

    # Only the file column is written back. A full save() would push the copy
    # loaded before the download over an edit made meanwhile, and would insert
    # the row again if the image was deleted while we were fetching it.
    stored = Image.objects.filter(id=image_id).update(image=image.image.name)
    if not stored:
        logger.warning(
            "download_image: image %s vanished during download, dropping file",
            image_id,
        )
        image.image.delete(save=False)
        return

    generate_image_thumbnails(image_id)
