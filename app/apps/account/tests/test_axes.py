import pytest
from django.urls import reverse


@pytest.fixture(autouse=True)
def enable_axes(settings):
    settings.AXES_ENABLED = True


@pytest.mark.django_db
def test_failed_logins_below_limit(client, user):
    user_obj, _ = user
    url = reverse("login")
    for _ in range(2):
        response = client.post(
            url, {"username": user_obj.username, "password": "wrongpass"}
        )
    assert response.status_code == 200


@pytest.mark.django_db
def test_lockout_after_three_failures(client, user):
    user_obj, _ = user
    url = reverse("login")
    for _ in range(3):
        client.post(url, {"username": user_obj.username, "password": "wrongpass"})

    response = client.post(url, {"username": user_obj.username, "password": "wrongpass"})
    assert response.status_code == 429
    assert b"Account Locked" in response.content


@pytest.mark.django_db
def test_successful_login_resets_counter(client, user):
    user_obj, password = user
    url = reverse("login")
    for _ in range(2):
        client.post(url, {"username": user_obj.username, "password": "wrongpass"})

    client.post(url, {"username": user_obj.username, "password": password})
    client.logout()

    for _ in range(2):
        response = client.post(
            url, {"username": user_obj.username, "password": "wrongpass"}
        )
    assert response.status_code == 200
