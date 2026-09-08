from django_ratelimit.exceptions import Ratelimited

from core.views import handler429


class RatelimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, Ratelimited):
            return handler429(request, exception)
        return None
