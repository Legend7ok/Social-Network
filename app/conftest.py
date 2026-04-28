import fakeredis
import pytest


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    r = fakeredis.FakeRedis()
    monkeypatch.setattr("apps.images.services.r", r)
    return r
