import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import Profile


@pytest.fixture(autouse=True)
def enable_axes(settings):
    settings.AXES_ENABLED = True


@pytest.fixture
def user(db):
    User = get_user_model()
    user_obj = User.objects.create_user(
        username="alice", email="alice@example.com", password="testpass123"
    )
    Profile.objects.create(user=user_obj)
    return user_obj


@pytest.mark.django_db
def test_failed_logins_below_limit(client, user):
    url = reverse("login")
    for _ in range(2):
        response = client.post(url, {"username": user.username, "password": "wrongpass"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_lockout_after_three_failures(client, user):
    url = reverse("login")
    for _ in range(3):
        client.post(url, {"username": user.username, "password": "wrongpass"})

    response = client.post(url, {"username": user.username, "password": "wrongpass"})
    assert response.status_code == 429
    assert b"Account Locked" in response.content


@pytest.mark.django_db
def test_successful_login_resets_counter(client, user):
    url = reverse("login")
    for _ in range(2):
        client.post(url, {"username": user.username, "password": "wrongpass"})

    client.post(url, {"username": user.username, "password": "testpass123"})
    client.logout()

    for _ in range(2):
        response = client.post(url, {"username": user.username, "password": "wrongpass"})
    assert response.status_code == 200
