import pytest
from django.core.cache import cache

from apps.images.services import record_image_view
from apps.images.tasks import refresh_image_ranking_cache



@pytest.mark.django_db
def test_refresh_image_ranking_cache_task_populates_cache(image, settings):
    record_image_view(image.id)

    refresh_image_ranking_cache()

    cached = cache.get(settings.IMAGE_RANKING_CACHE_KEY)
    assert cached is not None
    assert image in cached
