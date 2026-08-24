import io
from unittest.mock import MagicMock

import fakeredis
import pytest
import redis
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image as PILImage
from rest_framework.test import APIClient

from apps.images.models import Image

# Binds the shared tasks to the project's Celery app, which otherwise happens
# only once something imports the URLs. Without it a .delay() inside a task
# reaches for a broker instead of running inline, and whether that bites
# depends on the order tests happen to run in.
from config import celery_app  # noqa: E402,F401


def _png_bytes(size=(1, 1)):
    """Built by Pillow rather than pasted: a hand-written PNG with a broken
    checksum passes for a file everywhere except where it matters — the
    validation that reads it."""
    buffer = io.BytesIO()
    PILImage.new("RGB", size).save(buffer, format="PNG")
    return buffer.getvalue()


MINIMAL_PNG = _png_bytes()


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    r = fakeredis.FakeRedis()
    monkeypatch.setattr("apps.images.services.r", r)
    return r


@pytest.fixture
def make_user(db):
    def _make(username, email, password):
        User = get_user_model()
        user_obj = User.objects.create_user(
            username=username, email=email, password=password
        )
        return user_obj, password

    return _make


@pytest.fixture
def user(make_user):
    return make_user("alice", "alice@example.com", "testpass123")


@pytest.fixture
def second_user(make_user):
    return make_user("bob", "bob@example.com", "testpass456")


@pytest.fixture
def image(db, user):
    user_obj, _ = user
    img_file = SimpleUploadedFile("test.png", MINIMAL_PNG, content_type="image/png")
    return Image.objects.create(
        user=user_obj,
        title="Test Image",
        url="https://example.com/test.png",
        image=img_file,
        description="A test image",
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(user):
    user_obj, _ = user
    client = APIClient()
    client.force_authenticate(user=user_obj)
    return client


@pytest.fixture
def broken_redis(monkeypatch):
    """Every Redis call used by the view counters refuses to connect."""
    mock = MagicMock()
    mock.pipeline.side_effect = redis.ConnectionError("down")
    mock.get.side_effect = redis.ConnectionError("down")
    mock.mget.side_effect = redis.ConnectionError("down")
    mock.set.side_effect = redis.ConnectionError("down")
    mock.smembers.side_effect = redis.ConnectionError("down")
    monkeypatch.setattr("apps.images.services.r", mock)
    return mock
