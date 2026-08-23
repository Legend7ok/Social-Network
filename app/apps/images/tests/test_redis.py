import logging
from unittest.mock import MagicMock

import pytest
import redis
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.images.models import Image
from apps.images.services import (
    get_image_ranking,
    get_image_views,
    is_first_view,
    record_image_view,
)
from conftest import MINIMAL_PNG
from core.exceptions import RedisUnavailableError


@pytest.fixture
def broken_redis(monkeypatch):
    mock = MagicMock()
    mock.pipeline.side_effect = redis.ConnectionError("down")
    mock.zrange.side_effect = redis.ConnectionError("down")
    mock.zcard.side_effect = redis.ConnectionError("down")
    mock.get.side_effect = redis.ConnectionError("down")
    mock.mget.side_effect = redis.ConnectionError("down")
    mock.set.side_effect = redis.ConnectionError("down")
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


def test_record_image_view_updates_ranking_sorted_set(fake_redis):
    record_image_view(10)
    assert fake_redis.zscore("image_ranking", 10) == 1.0


def test_record_image_view_increments_ranking_score(fake_redis):
    record_image_view(10)
    record_image_view(10)
    record_image_view(10)
    assert fake_redis.zscore("image_ranking", 10) == 3.0


# ─── get_image_views ─────────────────────────────────────────────────────────


def test_get_image_views_returns_zero_for_new_image():
    assert get_image_views(99) == 0


def test_get_image_views_returns_current_count():
    record_image_view(5)
    record_image_view(5)
    assert get_image_views(5) == 2


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


# ─── get_image_ranking ───────────────────────────────────────────────────────


def test_get_image_ranking_empty_returns_empty_list():
    assert get_image_ranking() == []


def test_get_image_ranking_returns_python_ints():
    record_image_view(5)
    assert all(isinstance(i, int) for i in get_image_ranking())


def test_get_image_ranking_descending_order():
    for _ in range(3):
        record_image_view(1)
    for _ in range(5):
        record_image_view(2)
    record_image_view(3)
    assert get_image_ranking() == [2, 1, 3]


def test_get_image_ranking_respects_count_param():
    for image_id in range(1, 6):
        for _ in range(image_id):
            record_image_view(image_id)
    assert len(get_image_ranking(count=3)) == 3


def test_get_image_ranking_returns_all_when_fewer_than_count():
    record_image_view(1)
    record_image_view(2)
    assert len(get_image_ranking(count=10)) == 2


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


def test_get_image_ranking_raises_redis_unavailable_on_connection_error(broken_redis):
    with pytest.raises(RedisUnavailableError):
        get_image_ranking()


# ─── image_ranking view ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_image_ranking_redirects_anonymous_user(client):
    response = client.get(reverse("images:ranking"))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_image_ranking_returns_200(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:ranking"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_image_ranking_shows_most_viewed_first(client, user, image):
    user_obj, password = user
    img_file = SimpleUploadedFile("img2.png", MINIMAL_PNG, content_type="image/png")
    image2 = Image.objects.create(
        user=user_obj,
        title="Second Image",
        url="https://example.com/img2.png",
        image=img_file,
    )
    for _ in range(5):
        record_image_view(image2.id)
    record_image_view(image.id)

    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:ranking"))
    top3 = response.context["top3"]
    assert top3[0] == image2
    assert top3[1] == image


@pytest.mark.django_db
def test_image_ranking_excludes_stale_redis_entries(client, user, image):
    user_obj, password = user
    record_image_view(9999)  # ID не существует в БД
    record_image_view(image.id)

    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:ranking"))
    ids = [img.id for img in response.context["top3"]]
    assert 9999 not in ids
    assert image.id in ids
