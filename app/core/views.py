import logging

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

import redis as redis_lib

from apps.images.services import r as counters_redis

logger = logging.getLogger(__name__)


def healthz(request):
    """Liveness probe for the container runtime.

    Only the database decides the verdict. Without it the site cannot answer a
    single page, so a failure here has to be fatal. Redis is reported but never
    fatal: the site outlives its loss — pages render, uploads work, sign-in is
    guarded by the database — and killing a healthy web container over a cache
    would be a lie in the other direction. Redis reports on itself through its
    own health check.
    """
    checks = {"database": "ok", "redis": "ok"}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        logger.exception("healthz: database check failed")
        checks["database"] = "error"

    try:
        counters_redis.ping()
    except (redis_lib.ConnectionError, redis_lib.TimeoutError):
        # Logged at info: this is a note in the body, not an incident.
        logger.info("healthz: redis unreachable")
        checks["redis"] = "error"

    healthy = checks["database"] == "ok"
    return JsonResponse(
        {"status": "ok" if healthy else "error", "checks": checks},
        status=200 if healthy else 503,
    )


def handler429(request, exception=None):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {"detail": "Too many requests. Try again later."}, status=429
        )
    return render(request, "429.html", status=429)
