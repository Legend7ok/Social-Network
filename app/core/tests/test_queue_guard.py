import json

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse
from kombu.exceptions import OperationalError

from core.exceptions import QueueUnavailableError
from core.middleware import ServiceUnavailableMiddleware
from core.queue import ensure_queue_available


@pytest.fixture
def refuse_the_queue(monkeypatch):
    """Every attempt to reach the broker fails, as it would with Redis gone."""

    def refuse(*args, **kwargs):
        raise OperationalError("broker is gone")

    monkeypatch.setattr(
        "core.queue.celery_app.connection_for_write",
        lambda *a, **kw: type("Conn", (), {"ensure_connection": refuse})(),
    )


@pytest.fixture
def queue_answers(monkeypatch):
    """A broker that accepts the connection. Faked rather than run: the suite
    must not need a Redis of its own to say what this code does."""
    monkeypatch.setattr(
        "core.queue.celery_app.connection_for_write",
        lambda *a, **kw: type(
            "Conn", (), {"ensure_connection": lambda *a, **kw: None}
        )(),
    )


def test_check_passes_when_the_broker_answers(queue_answers):
    ensure_queue_available()


def test_check_raises_when_the_broker_is_gone(refuse_the_queue):
    with pytest.raises(QueueUnavailableError):
        ensure_queue_available()


def test_middleware_answers_503_with_a_page():
    middleware = ServiceUnavailableMiddleware(get_response=lambda r: None)
    request = RequestFactory().post("/")

    response = middleware.process_exception(request, QueueUnavailableError("down"))

    assert response.status_code == 503


def test_middleware_answers_503_as_json_when_asked_for_json():
    middleware = ServiceUnavailableMiddleware(get_response=lambda r: None)
    request = RequestFactory().post("/", HTTP_ACCEPT="application/json")

    response = middleware.process_exception(request, QueueUnavailableError("down"))

    assert response.status_code == 503
    assert json.loads(response.content) == {"detail": "Service temporarily unavailable"}


def test_middleware_leaves_other_failures_alone():
    """A real bug must stay a 500; hiding it behind 503 would say the site is
    fine and invite the person to keep trying."""
    middleware = ServiceUnavailableMiddleware(get_response=lambda r: None)

    assert middleware.process_exception(RequestFactory().get("/"), ValueError()) is None


@pytest.fixture
def registration_finds_no_queue(monkeypatch):
    """Puts the refusal where the view reads it, since the view bound the check
    by name at import time."""

    def refuse():
        raise QueueUnavailableError("broker is gone")

    monkeypatch.setattr("apps.account.views.ensure_queue_available", refuse)


@pytest.mark.django_db
def test_registration_writes_nothing_when_the_queue_is_gone(
    client, registration_finds_no_queue
):
    """The whole point of checking first: the answer must be true. A refusal
    after the account exists would send the person back to a form that then
    tells them the name is taken."""
    response = client.post(
        reverse("register"),
        {
            "username": "hopeful",
            "email": "hopeful@example.com",
            "password": "SomePass123!",
        },
    )

    assert response.status_code == 503
    assert not get_user_model().objects.filter(username="hopeful").exists()
