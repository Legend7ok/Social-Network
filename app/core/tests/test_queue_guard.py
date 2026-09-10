import json

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from django.urls import reverse
from kombu.exceptions import OperationalError

from apps.images.models import Image
from conftest import MINIMAL_PNG
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


def _refuse():
    raise QueueUnavailableError("broker is gone")


@pytest.fixture
def account_views_find_no_queue(monkeypatch):
    """Puts the refusal where the views read it, since each bound the check by
    name at import time. One patch covers registration, the avatar and the
    profile form - they all live in the same module."""
    monkeypatch.setattr("apps.account.views.ensure_queue_available", _refuse)


@pytest.fixture
def image_views_find_no_queue(monkeypatch):
    monkeypatch.setattr("apps.images.views.ensure_queue_available", _refuse)


@pytest.mark.django_db
def test_registration_writes_nothing_when_the_queue_is_gone(
    client, account_views_find_no_queue
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


@pytest.mark.django_db
def test_a_new_avatar_is_refused_when_the_queue_is_gone(
    client, user, account_views_find_no_queue
):
    """A photo is stored and then cut into three sizes by a task. Letting it
    through without the task leaves an avatar nobody sized, and the person is
    told the upload failed while the file is already in the bucket."""
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    photo = SimpleUploadedFile("avatar.png", MINIMAL_PNG, content_type="image/png")

    response = client.post(reverse("profile_photo"), {"photo": photo})

    assert response.status_code == 503
    user_obj.profile.refresh_from_db()
    assert not user_obj.profile.photo


@pytest.mark.django_db
def test_the_rest_of_the_profile_still_saves_when_the_queue_is_gone(
    client, user, account_views_find_no_queue
):
    """Only a photo brings background work with it. Refusing a change of name
    over a queue nothing was going to use would be a refusal for its own sake."""
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(
        reverse("edit"),
        {"first_name": "Renamed", "last_name": "", "email": user_obj.email},
    )

    assert response.status_code == 302
    user_obj.refresh_from_db()
    assert user_obj.first_name == "Renamed"


@pytest.mark.django_db
def test_deleting_a_picture_is_refused_when_the_queue_is_gone(
    client, user, image, image_views_find_no_queue
):
    """The file in the bucket, the feed entries and the view counters are all
    cleaned up by a task. Deleting the row without it leaves every one of them
    behind with nothing left to name them."""
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(reverse("images:delete", args=[image.id]))

    assert response.status_code == 503
    assert Image.objects.filter(pk=image.pk).exists()
