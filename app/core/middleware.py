import logging

from django.http import JsonResponse
from django.shortcuts import render
from django_ratelimit.exceptions import Ratelimited

from core.exceptions import ServiceUnavailableError
from core.views import handler429

logger = logging.getLogger(__name__)


class RatelimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, Ratelimited):
            return handler429(request, exception)
        return None


class ServiceUnavailableMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, ServiceUnavailableError):
            logger.error("Service unavailable: %s", exception, exc_info=True)
            if "application/json" in request.headers.get("Accept", ""):
                return JsonResponse(
                    {"detail": "Service temporarily unavailable"}, status=503
                )
            return render(request, "503.html", status=503)
        return None
