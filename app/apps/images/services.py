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
            pipe.zincrby("image_ranking", 1, image_id)
            delta, _, _ = pipe.execute()
        return delta
    except _REDIS_ERRORS:
        logger.error(
            "Redis unavailable: record_image_view failed for image %s",
            image_id,
            exc_info=True,
        )
        return 0


def get_image_ranking(start=0, count=10):
    try:
        end = start + count - 1
        ids = r.zrange("image_ranking", start, end, desc=True)
        return [int(id) for id in ids]
    except _REDIS_ERRORS as e:
        raise RedisUnavailableError("Redis unavailable") from e


def get_image_ranking_count():
    try:
        return r.zcard("image_ranking")
    except _REDIS_ERRORS as e:
        raise RedisUnavailableError("Redis unavailable") from e


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
