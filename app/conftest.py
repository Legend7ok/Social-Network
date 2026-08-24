from unittest.mock import MagicMock

import fakeredis
import pytest
import redis
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.images.models import Image

MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


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
def staff_user(db):
    """A service account: it must stay out of every public listing."""
    user_obj = get_user_model().objects.create_user(
        username="root", email="root@example.com", password="testpass789", is_staff=True
    )
    return user_obj, "testpass789"


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
