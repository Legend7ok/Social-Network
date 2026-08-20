import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.account.authentication import EmailAuthBackend


@pytest.fixture
def backend():
    return EmailAuthBackend()


# ─── authenticate ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_authenticate_valid_email_returns_user(backend, user):
    user_obj, password = user
    result = backend.authenticate(
        request=None, username=user_obj.email, password=password
    )
    assert result == user_obj


@pytest.mark.django_db
def test_authenticate_wrong_password_returns_none(backend, user):
    user_obj, _ = user
    result = backend.authenticate(
        request=None, username=user_obj.email, password="wrongpass"
    )
    assert result is None


@pytest.mark.django_db
def test_authenticate_nonexistent_email_returns_none(backend):
    result = backend.authenticate(
        request=None, username="nobody@example.com", password="pass"
    )
    assert result is None


@pytest.mark.django_db
def test_authenticate_accepts_any_casing(backend, user):
    user_obj, password = user
    result = backend.authenticate(
        request=None, username=user_obj.email.upper(), password=password
    )
    assert result == user_obj


@pytest.mark.django_db
def test_authenticate_rejects_inactive_user(backend, user):
    user_obj, password = user
    user_obj.is_active = False
    user_obj.save()

    result = backend.authenticate(
        request=None, username=user_obj.email, password=password
    )
    assert result is None


@pytest.mark.django_db
def test_authenticate_blank_email_returns_none(backend, make_user):
    """A blank address is shared by every social account that came without one,
    so it must never be treated as a lookup value."""
    make_user("nomail", "", "testpass789")

    result = backend.authenticate(request=None, username="", password="testpass789")
    assert result is None


@pytest.mark.django_db
def test_duplicate_email_rejected_whatever_the_case():
    """Two accounts on one address used to break login for both of them; the
    database now refuses the second one, casing included."""
    User = get_user_model()
    User.objects.create_user(
        username="user1", email="same@example.com", password="pass1"
    )
    with pytest.raises(IntegrityError):
        User.objects.create_user(
            username="user2", email="SAME@example.com", password="pass2"
        )


@pytest.mark.django_db
def test_blank_emails_stay_allowed():
    """Social logins may hand us no address at all, so blanks must not collide."""
    User = get_user_model()
    User.objects.create_user(username="user1", email="", password="pass1")
    User.objects.create_user(username="user2", email="", password="pass2")

    assert User.objects.filter(email="").count() == 2


# ─── social login ─────────────────────────────────────────────────────────────


def test_social_login_associates_before_it_creates():
    """Signing in with Google or GitHub on an address that already has an
    account must join the two, not attempt a second row the index refuses."""
    steps = settings.SOCIAL_AUTH_PIPELINE

    assert steps.index(
        "social_core.pipeline.social_auth.associate_by_email"
    ) < steps.index("social_core.pipeline.user.create_user")


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
