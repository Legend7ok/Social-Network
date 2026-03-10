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

    assert response.status_code == 200

    dashboard_response = client.get(reverse("dashboard"))
    assert dashboard_response.status_code == 302

