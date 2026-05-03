import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.images.services import record_image_view
from apps.images.tasks import refresh_image_ranking_cache


@pytest.mark.django_db
def test_image_ranking_cache_miss_populates_cache(client, user, image, settings):
    user_obj, password = user
    record_image_view(image.id)
    client.login(username=user_obj.username, password=password)

    assert cache.get(settings.IMAGE_RANKING_CACHE_KEY) is None
    client.get(reverse("images:ranking"))
    assert cache.get(settings.IMAGE_RANKING_CACHE_KEY) is not None


@pytest.mark.django_db
def test_image_ranking_served_from_cache(client, user, image, settings):
    user_obj, password = user
    cache.set(
        settings.IMAGE_RANKING_CACHE_KEY, [image], settings.IMAGE_RANKING_CACHE_TTL
    )

    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:ranking"))

    assert response.context["most_viewed"] == [image]


@pytest.mark.django_db
def test_refresh_image_ranking_cache_task_populates_cache(image, settings):
    record_image_view(image.id)

    refresh_image_ranking_cache()

    cached = cache.get(settings.IMAGE_RANKING_CACHE_KEY)
    assert cached is not None
    assert image in cached
