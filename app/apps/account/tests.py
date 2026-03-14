from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import Profile


@pytest.fixture
def user(db):
    user_model = get_user_model()
    password = "testpass123"
    user_obj = user_model.objects.create_user(
        username="alice",
        first_name="Alice",
        email="alice@example.com",
        password=password,
    )
    Profile.objects.create(user=user_obj)
    return user_obj, password


@pytest.mark.django_db
def test_login_page_loads(client):
    response = client.get(reverse("login"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_logout_requires_post(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("logout"))

    assert response.status_code == 405


@pytest.mark.django_db
def test_logout_post_logs_out(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(reverse("logout"))

    assert response.status_code == 302

    dashboard_response = client.get(reverse("dashboard"))
    assert dashboard_response.status_code == 302


@pytest.mark.django_db
def test_register_creates_profile(client):
    payload = {
        "username": "bob",
        "first_name": "Bob",
        "email": "bob@example.com",
        "password": "secret123",
        "password2": "secret123",
    }

    response = client.post(reverse("register"), data=payload)

    assert response.status_code == 200

    user_model = get_user_model()
    user_obj = user_model.objects.get(username="bob")
    assert Profile.objects.filter(user=user_obj).exists()


@pytest.mark.django_db
def test_edit_requires_login(client):
    response = client.get(reverse("edit"))

    assert response.status_code == 302


@pytest.mark.django_db
def test_edit_updates_profile(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    payload = {
        "first_name": "AliceUpdated",
        "last_name": "Smith",
        "email": "alice.updated@example.com",
        "date_of_birth": date(1990, 1, 1),
    }

    response = client.post(reverse("edit"), data=payload)

    assert response.status_code == 200

    user_obj.refresh_from_db()
    user_obj.profile.refresh_from_db()

    assert user_obj.first_name == "AliceUpdated"
    assert user_obj.last_name == "Smith"
    assert user_obj.email == "alice.updated@example.com"
    assert user_obj.profile.date_of_birth == date(1990, 1, 1)
