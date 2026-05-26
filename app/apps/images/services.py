import logging

import redis
from django.conf import settings

from core.exceptions import RedisUnavailableError

logger = logging.getLogger(__name__)

r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    socket_connect_timeout=2,
    socket_timeout=2,
)

_REDIS_ERRORS = (redis.ConnectionError, redis.TimeoutError)


def record_image_view(image_id):
    try:
        with r.pipeline() as pipe:
            pipe.incr(f"image:{image_id}:views")
            pipe.zincrby("image_ranking", 1, image_id)
            total_views, _ = pipe.execute()
        return total_views
    except _REDIS_ERRORS:
        logger.error("Redis unavailable: record_image_view failed for image %s", image_id, exc_info=True)
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
    try:
        return int(r.get(f"image:{image_id}:views") or 0)
    except _REDIS_ERRORS as e:
        raise RedisUnavailableError("Redis unavailable") from e


def get_images_views(image_ids):
    if not image_ids:
        return {}
    try:
        keys = [f"image:{id}:views" for id in image_ids]
        values = r.mget(keys)
        return {id: int(v or 0) for id, v in zip(image_ids, values)}
    except _REDIS_ERRORS as e:
        raise RedisUnavailableError("Redis unavailable") from e


def is_first_view(image_id, viewer_key, ttl=3600):
    try:
        key = f"image:{image_id}:view:{viewer_key}"
        return bool(r.set(key, 1, ex=ttl, nx=True))
    except _REDIS_ERRORS:
        logger.error("Redis unavailable: is_first_view failed for image %s", image_id, exc_info=True)
        return False
