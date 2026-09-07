import json

import pytest
import redis
from django.urls import reverse


@pytest.mark.django_db
def test_healthz_is_ok_when_everything_answers(client, fake_redis):
    """fake_redis, so the verdict comes from our code and not from whether a
    real Redis happens to answer within the timeout."""
    response = client.get(reverse("healthz"))

    assert response.status_code == 200
    assert json.loads(response.content) == {
        "status": "ok",
        "checks": {"database": "ok", "redis": "ok"},
    }


@pytest.mark.django_db
def test_healthz_stays_ok_without_redis(client, monkeypatch):
    """The site outlives a dead Redis, so the container must not be killed for
    it — the loss is reported in the body instead."""

    def refuse():
        raise redis.ConnectionError("down")

    monkeypatch.setattr("apps.images.services.r.ping", refuse)

    response = client.get(reverse("healthz"))

    assert response.status_code == 200
    body = json.loads(response.content)
    assert body["status"] == "ok"
    assert body["checks"]["redis"] == "error"


@pytest.mark.django_db
def test_healthz_fails_without_the_database(client, monkeypatch):
    """Nothing can be served without it, so this one is fatal."""

    def refuse(*args, **kwargs):
        raise Exception("no database")

    monkeypatch.setattr("django.db.backends.utils.CursorWrapper.execute", refuse)

    response = client.get(reverse("healthz"))

    assert response.status_code == 503
    body = json.loads(response.content)
    assert body["status"] == "error"
    assert body["checks"]["database"] == "error"


@pytest.mark.django_db
def test_healthz_needs_no_account(client, fake_redis):
    """The container runtime has no session to sign in with."""
    response = client.get(reverse("healthz"))

    assert response.status_code == 200
