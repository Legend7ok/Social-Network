import pytest
from django.contrib.auth import get_user_model

from apps.account.authentication import EmailAuthBackend


@pytest.fixture
def backend():
    return EmailAuthBackend()


# ─── authenticate ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_authenticate_valid_email_returns_user(backend, user):
    user_obj, password = user
    result = backend.authenticate(request=None, username=user_obj.email, password=password)
    assert result == user_obj


@pytest.mark.django_db
def test_authenticate_wrong_password_returns_none(backend, user):
    user_obj, _ = user
    result = backend.authenticate(request=None, username=user_obj.email, password="wrongpass")
    assert result is None


@pytest.mark.django_db
def test_authenticate_nonexistent_email_returns_none(backend):
    result = backend.authenticate(request=None, username="nobody@example.com", password="pass")
    assert result is None


@pytest.mark.django_db
def test_authenticate_duplicate_email_returns_none(backend, db):
    User = get_user_model()
    User.objects.create_user(username="user1", email="same@example.com", password="pass1")
    User.objects.create_user(username="user2", email="same@example.com", password="pass2")
    result = backend.authenticate(request=None, username="same@example.com", password="pass1")
    assert result is None


# ─── get_user ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_get_user_valid_id_returns_user(backend, user):
    user_obj, _ = user
    result = backend.get_user(user_obj.pk)
    assert result == user_obj


@pytest.mark.django_db
def test_get_user_invalid_id_returns_none(backend):
    result = backend.get_user(9999)
    assert result is None
