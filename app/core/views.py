from django.http import JsonResponse
from django.shortcuts import render


def handler429(request, exception=None):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"detail": "Too many requests. Try again later."}, status=429)
    return render(request, "429.html", status=429)
