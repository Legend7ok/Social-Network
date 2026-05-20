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


def get_image_ranking(start=0, count=10):
    end = start + count - 1
    ids = r.zrange("image_ranking", start, end, desc=True)
    return [int(id) for id in ids]


def get_image_ranking_count():
    return r.zcard("image_ranking")


def get_image_views(image_id):
    return int(r.get(f"image:{image_id}:views") or 0)


def get_images_views(image_ids):
    if not image_ids:
        return {}
    keys = [f"image:{id}:views" for id in image_ids]
    values = r.mget(keys)
    return {id: int(v or 0) for id, v in zip(image_ids, values)}


def is_first_view(image_id, viewer_key, ttl=3600):
    key = f"image:{image_id}:view:{viewer_key}"
    return bool(r.set(key, 1, ex=ttl, nx=True))
