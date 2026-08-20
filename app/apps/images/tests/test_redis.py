import logging
from unittest.mock import MagicMock

import pytest
import redis

from apps.images.models import Image
from apps.images.services import (
    DIRTY_IMAGES_KEY,
    get_dirty_image_ids,
    get_image_views,
    get_images_views,
    is_first_view,
    record_image_view,
)
from core.exceptions import RedisUnavailableError


@pytest.fixture
def broken_redis(monkeypatch):
    mock = MagicMock()
    mock.pipeline.side_effect = redis.ConnectionError("down")
    mock.get.side_effect = redis.ConnectionError("down")
    mock.mget.side_effect = redis.ConnectionError("down")
    mock.set.side_effect = redis.ConnectionError("down")
    mock.smembers.side_effect = redis.ConnectionError("down")
    monkeypatch.setattr("apps.images.services.r", mock)
    return mock


# ─── record_image_view ───────────────────────────────────────────────────────


def test_record_image_view_starts_at_one():
    assert record_image_view(42) == 1


def test_record_image_view_increments_on_each_call():
    record_image_view(1)
    assert record_image_view(1) == 2


def test_record_image_view_different_images_are_independent():
    record_image_view(1)
    record_image_view(1)
    assert record_image_view(2) == 1


def test_record_image_view_marks_image_as_dirty(fake_redis):
    record_image_view(10)
    assert fake_redis.smembers(DIRTY_IMAGES_KEY) == {b"10"}


# ─── get_image_views ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_get_image_views_returns_zero_for_new_image():
    assert get_image_views(99) == 0


@pytest.mark.django_db
def test_get_image_views_returns_current_count():
    record_image_view(5)
    record_image_view(5)
    assert get_image_views(5) == 2


@pytest.mark.django_db
def test_get_image_views_adds_delta_to_stored_total(image):
    Image.objects.filter(id=image.id).update(total_views=100)
    record_image_view(image.id)
    assert get_image_views(image.id) == 101


@pytest.mark.django_db
def test_get_images_views_adds_delta_to_stored_total(image):
    Image.objects.filter(id=image.id).update(total_views=7)
    record_image_view(image.id)
    record_image_view(image.id)
    assert get_images_views([image.id]) == {image.id: 9}


@pytest.mark.django_db
def test_get_images_views_empty_input_returns_empty_dict():
    assert get_images_views([]) == {}


# ─── is_first_view ────────────────────────────────────────────────────────────


def test_is_first_view_returns_true_on_first_call():
    assert is_first_view(1, "user:42") is True


def test_is_first_view_returns_false_on_repeat():
    is_first_view(1, "user:42")
    assert is_first_view(1, "user:42") is False


def test_is_first_view_different_viewers_are_independent():
    assert is_first_view(1, "user:1") is True
    assert is_first_view(1, "user:2") is True


def test_is_first_view_different_images_are_independent():
    assert is_first_view(1, "user:1") is True
    assert is_first_view(2, "user:1") is True


# ─── connection error handling ───────────────────────────────────────────────


def test_record_image_view_returns_zero_on_connection_error(broken_redis):
    assert record_image_view(1) == 0


def test_record_image_view_logs_on_connection_error(broken_redis, caplog):
    with caplog.at_level(logging.ERROR, logger="apps.images.services"):
        record_image_view(1)
    assert "record_image_view" in caplog.text


def test_is_first_view_returns_false_on_connection_error(broken_redis):
    assert is_first_view(1, "user:1") is False


def test_is_first_view_logs_on_connection_error(broken_redis, caplog):
    with caplog.at_level(logging.ERROR, logger="apps.images.services"):
        is_first_view(1, "user:1")
    assert "is_first_view" in caplog.text


def test_get_dirty_image_ids_raises_redis_unavailable_on_connection_error(broken_redis):
    # The flush task must fail loudly instead of silently skipping a run.
    with pytest.raises(RedisUnavailableError):
        get_dirty_image_ids()


@pytest.mark.django_db
def test_get_image_views_falls_back_to_stored_total(broken_redis, image):
    Image.objects.filter(id=image.id).update(total_views=42)
    assert get_image_views(image.id) == 42


@pytest.mark.django_db
def test_get_images_views_falls_back_to_stored_total(broken_redis, image):
    Image.objects.filter(id=image.id).update(total_views=42)
    assert get_images_views([image.id]) == {image.id: 42}
