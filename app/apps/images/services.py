import logging

import redis
from django.conf import settings

from core.exceptions import RedisUnavailableError

from .models import Image

logger = logging.getLogger(__name__)

r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    socket_connect_timeout=2,
    socket_timeout=2,
)

_REDIS_ERRORS = (redis.ConnectionError, redis.TimeoutError)

# Redis is a write buffer, not the source of truth: a counter holds only the
# views collected since the last flush into Image.total_views, and every image
# touched since then is listed in the dirty set so the flush task knows where to
# look. Losing Redis therefore costs at most one flush interval of views.
DIRTY_IMAGES_KEY = "image_views:dirty"


def _delta_key(image_id):
    return f"image:{image_id}:views"


def record_image_view(image_id):
    try:
        with r.pipeline() as pipe:
            pipe.incr(_delta_key(image_id))
            pipe.sadd(DIRTY_IMAGES_KEY, image_id)
            delta, _ = pipe.execute()
        return delta
    except _REDIS_ERRORS:
        logger.error(
            "Redis unavailable: record_image_view failed for image %s",
            image_id,
            exc_info=True,
        )
        return 0


def forget_image_views(image_id):
    """
    Drop the counters of an image that no longer exists.

    Failure is not fatal: the next flush finds no row to update and clears the
    leftovers anyway, so the buffer heals itself.
    """
    try:
        with r.pipeline() as pipe:
            pipe.delete(_delta_key(image_id))
            pipe.srem(DIRTY_IMAGES_KEY, image_id)
            pipe.execute()
    except _REDIS_ERRORS:
        logger.error(
            "Redis unavailable: forget_image_views failed for image %s",
            image_id,
            exc_info=True,
        )


def get_dirty_image_ids():
    """Images that collected views since the last flush."""
    try:
        return sorted(int(image_id) for image_id in r.smembers(DIRTY_IMAGES_KEY))
    except _REDIS_ERRORS as e:
        raise RedisUnavailableError("Redis unavailable") from e


def read_view_deltas(image_ids):
    """Buffered view counts, keyed by image id."""
    try:
        values = r.mget([_delta_key(image_id) for image_id in image_ids])
    except _REDIS_ERRORS as e:
        raise RedisUnavailableError("Redis unavailable") from e
    return {image_id: int(value or 0) for image_id, value in zip(image_ids, values)}


def clear_view_deltas(deltas):
    """
    Give back the counts that made it into the database.

    Subtracts instead of resetting, so views that arrived while the flush was
    running survive; an image only leaves the dirty set once its counter is
    fully drained.
    """
    try:
        with r.pipeline() as pipe:
            for image_id, delta in deltas.items():
                pipe.decrby(_delta_key(image_id), delta)
            remainders = pipe.execute()
        drained = [
            image_id
            for image_id, remainder in zip(deltas, remainders)
            if remainder <= 0
        ]
        if drained:
            r.srem(DIRTY_IMAGES_KEY, *drained)
    except _REDIS_ERRORS as e:
        raise RedisUnavailableError("Redis unavailable") from e
    return drained


def get_image_views(image_id):
    """Stored views plus the delta Redis has not flushed into the database yet."""
    stored = (
        Image.objects.filter(id=image_id).values_list("total_views", flat=True).first()
        or 0
    )
    try:
        return stored + int(r.get(_delta_key(image_id)) or 0)
    except _REDIS_ERRORS:
        logger.error(
            "Redis unavailable: serving stored views for image %s",
            image_id,
            exc_info=True,
        )
        return stored


def get_images_views(image_ids):
    """Same as get_image_views, for a page of images at once."""
    if not image_ids:
        return {}
    stored = dict(
        Image.objects.filter(id__in=image_ids).values_list("id", "total_views")
    )
    totals = {image_id: stored.get(image_id, 0) for image_id in image_ids}
    try:
        deltas = r.mget([_delta_key(image_id) for image_id in image_ids])
    except _REDIS_ERRORS:
        logger.error(
            "Redis unavailable: serving stored views for %s images",
            len(image_ids),
            exc_info=True,
        )
        return totals
    for image_id, delta in zip(image_ids, deltas):
        totals[image_id] += int(delta or 0)
    return totals


def apply_live_views(images):
    """Overlay the counts still buffered in Redis on the stored ones, for the
    page of images about to be rendered. Callers pass a list, not a queryset:
    the attribute has to survive the template iterating over it."""
    views = get_images_views([image.id for image in images])
    for image in images:
        image.total_views = views.get(image.id, image.total_views)


def is_first_view(image_id, viewer_key, ttl=3600):
    try:
        key = f"image:{image_id}:view:{viewer_key}"
        return bool(r.set(key, 1, ex=ttl, nx=True))
    except _REDIS_ERRORS:
        logger.error(
            "Redis unavailable: is_first_view failed for image %s",
            image_id,
            exc_info=True,
        )
        return False
