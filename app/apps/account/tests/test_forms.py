import pytest

from apps.account.forms import (
    EmailOrUsernameAuthenticationForm,
    UserEditForm,
    UserRegistrationForm,
)

STRONG_PASSWORD = "Str0ngPassphrase!42"


def registration_data(**overrides):
    data = {
        "username": "bob",
        "email": "bob@example.com",
        "password": STRONG_PASSWORD,
    }
    data.update(overrides)
    return data


# ─── registration ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_blank_password_is_reported_not_crashed():
    """The previous form read a missing key here and answered with a 500."""
    form = UserRegistrationForm(registration_data(password=""))

    assert not form.is_valid()
    assert form.errors["password"]


@pytest.mark.django_db
def test_password_matching_the_username_is_rejected():
    form = UserRegistrationForm(
        registration_data(username="bobmarley", password="bobmarley")
    )

    assert not form.is_valid()
    assert form.errors["password"]


@pytest.mark.django_db
def test_username_taken_in_another_case_is_rejected(user):
    form = UserRegistrationForm(
        registration_data(username="ALICE", email="new@example.com")
    )

    assert not form.is_valid()
    assert form.errors["username"]


@pytest.mark.django_db
def test_email_taken_in_another_case_is_rejected(user):
    form = UserRegistrationForm(registration_data(email="ALICE@EXAMPLE.COM"))

    assert not form.is_valid()
    assert form.errors["email"]


@pytest.mark.django_db
def test_saving_lower_cases_the_email_and_hashes_the_password():
    form = UserRegistrationForm(registration_data(email="BOB@Example.COM"))
    assert form.is_valid(), form.errors

    new_user = form.save()

    assert new_user.email == "bob@example.com"
    assert new_user.password != STRONG_PASSWORD
    assert new_user.check_password(STRONG_PASSWORD)


# ─── sign in ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_sign_in_accepts_an_address_longer_than_a_username(make_user):
    """Django sizes this field after the username column (150), but addresses
    are allowed 254 characters."""
    long_email = "a" * 240 + "@e.com"
    user_obj, password = make_user("longmail", long_email, "testpass321")

    form = EmailOrUsernameAuthenticationForm(
        data={"username": long_email, "password": password}
    )

    assert form.is_valid(), form.errors
    assert form.get_user() == user_obj


# ─── profile edit ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_edit_rejects_an_email_owned_by_someone_else(user, second_user):
    user_obj, _ = user
    other, _ = second_user

    form = UserEditForm(
        {"first_name": "", "last_name": "", "email": other.email.upper()},
        instance=user_obj,
    )

    assert not form.is_valid()
    assert form.errors["email"]


@pytest.mark.django_db
def test_edit_accepts_your_own_email_in_another_case(user):
    """Re-saving your own profile must not trip the uniqueness check."""
    user_obj, _ = user

    form = UserEditForm(
        {"first_name": "", "last_name": "", "email": user_obj.email.upper()},
        instance=user_obj,
    )

    assert form.is_valid(), form.errors
