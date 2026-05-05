import redis
from django.conf import settings


r = redis.Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB
)


def record_image_view(image_id):
    with r.pipeline() as pipe:
        pipe.incr(f"image:{image_id}:views")
        pipe.zincrby("image_ranking", 1, image_id)
        total_views, _ = pipe.execute()
    return total_views


def get_image_ranking(count=10):
    image_ranking = r.zrange("image_ranking", 0, -1, desc=True)[:count]
    return [int(id) for id in image_ranking]


def get_image_views(image_id):
    return int(r.get(f"image:{image_id}:views") or 0)


def is_first_view(image_id, viewer_key, ttl=3600):
    key = f"image:{image_id}:view:{viewer_key}"
    return bool(r.set(key, 1, ex=ttl, nx=True))
