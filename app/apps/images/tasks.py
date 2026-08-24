import io
import logging
from urllib.parse import urljoin

import requests
from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models import F, Q
from sorl.thumbnail import delete as delete_thumbnails
from sorl.thumbnail import get_thumbnail

from apps.actions.models import Action
from core.url_safety import validate_public_url
from core.validators import (
    IMAGE_FORMAT_EXTENSIONS,
    VALID_IMAGE_CONTENT_TYPES,
    validate_image_content,
)

from .models import Image
from .services import (
    clear_view_deltas,
    forget_image_views,
    get_dirty_image_ids,
    read_view_deltas,
)

logger = logging.getLogger(__name__)

FLUSH_BATCH_SIZE = 500
DOWNLOAD_TIMEOUT = 10
MAX_REDIRECTS = 5


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


def _discard(image, reason):
    logger.warning("download_image: discarding image %s, %s", image.id, reason)
    image.delete()


def _fetch(url):
    """Walk the redirect chain by hand so its length is ours to bound and every
    hop is checked before we connect: a public link may point anywhere next."""
    for _ in range(MAX_REDIRECTS):
        validate_public_url(url)
        response = requests.get(
            url, timeout=DOWNLOAD_TIMEOUT, stream=True, allow_redirects=False
        )
        if not response.is_redirect:
            return response
        with response:
            url = urljoin(url, response.headers["Location"])
    raise requests.TooManyRedirects(url)


def _read_body(response):
    """Read the response in chunks, giving up as soon as it outgrows the limit."""
    chunks = []
    size = 0
    for chunk in response.iter_content(chunk_size=8192):
        size += len(chunk)
        if size > settings.MAX_UPLOAD_SIZE:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


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

    # The queue promises delivery at least once, so the same bookmark can be
    # handed out twice; downloading again would leave the first file orphaned
    # in the bucket, because stored names are never reused.
    if image.image:
        logger.info("download_image: image %s already has a file, skipping", image_id)
        return

    try:
        response = _fetch(url)
    except requests.TooManyRedirects:
        # Retrying would only walk the same chain again.
        _discard(image, "the link redirects in circles")
        return
    except ValidationError as error:
        _discard(image, error.messages[0])
        return

    with response:
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
        if content_type.lower() not in VALID_IMAGE_CONTENT_TYPES:
            _discard(image, f"the server answered with {content_type or 'no type'}")
            return

        declared_size = response.headers.get("Content-Length", "")
        if declared_size.isdigit() and int(declared_size) > settings.MAX_UPLOAD_SIZE:
            _discard(image, "the file is larger than the limit")
            return

        body = _read_body(response)

    if body is None:
        _discard(image, "the file is larger than the limit")
        return

    try:
        image_format = validate_image_content(io.BytesIO(body))
    except ValidationError:
        # The headers can say anything; this is the first look at the bytes.
        _discard(image, "the file is not an image we accept")
        return

    # image.slug, not the raw title: a title without letters slugifies to an
    # empty string and would store a nameless ".jpg".
    name = f"{image.slug}.{IMAGE_FORMAT_EXTENSIONS[image_format]}"
    image.image.save(name, ContentFile(body), save=False)

    # Only the file column is written back. A full save() would push the copy
    # loaded before the download over an edit made meanwhile, and would insert
    # the row again if the image was deleted while we were fetching it.
    # Writing only while the column is still empty settles the race with a
    # second run of the same task: the loser drops its file instead of
    # replacing the winner's and leaving it behind in the bucket.
    stored = (
        Image.objects.filter(id=image_id)
        .filter(Q(image="") | Q(image__isnull=True))
        .update(image=image.image.name)
    )
    if not stored:
        logger.warning(
            "download_image: image %s is no longer waiting for this file, dropping it",
            image_id,
        )
        image.image.delete(save=False)
        return

    generate_image_thumbnails(image_id)
