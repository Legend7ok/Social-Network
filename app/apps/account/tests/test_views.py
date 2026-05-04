from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.account.models import Profile


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


# ─── user_login POST ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_login_post_valid_credentials_redirects_to_dashboard(client, user):
    user_obj, password = user
    response = client.post(
        reverse("login"), {"username": user_obj.username, "password": password}
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("dashboard")


# ─── dashboard ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    response = client.get(reverse("dashboard"))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_dashboard_returns_200(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert response.context["section"] == "dashboard"


# ─── register ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_register_get_shows_form(client):
    response = client.get(reverse("register"))
    assert response.status_code == 200
    assert "user_form" in response.context


@pytest.mark.django_db
def test_register_post_password_mismatch_shows_errors(client):
    response = client.post(
        reverse("register"),
        {
            "username": "bob",
            "first_name": "Bob",
            "email": "bob@example.com",
            "password": "secret123",
            "password2": "different",
        },
    )
    assert response.status_code == 200
    assert response.context["user_form"].errors


# ─── edit ─────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_edit_post_invalid_form_shows_error_message(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(
        reverse("edit"),
        {"first_name": "Alice", "last_name": "", "email": "not-an-email"},
    )
    assert response.status_code == 200
    msgs = [m.message for m in get_messages(response.wsgi_request)]
    assert any("Error" in m for m in msgs)


# ─── user_list ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_user_list_requires_login(client):
    response = client.get(reverse("user_list"))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_user_list_returns_200(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("user_list"))
    assert response.status_code == 200
    assert response.context["section"] == "people"


# ─── user_detail ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_user_detail_returns_200(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("user_detail", args=[user_obj.username]))
    assert response.status_code == 200
    assert response.context["user"] == user_obj


@pytest.mark.django_db
def test_user_detail_returns_404_for_unknown_user(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("user_detail", args=["nobody"]))
    assert response.status_code == 404
