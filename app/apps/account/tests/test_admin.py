import pytest
from django.urls import NoReverseMatch, reverse

from apps.account.models import Profile


@pytest.mark.django_db
def test_user_change_form_carries_the_profile(admin_client, user):
    user_obj, _ = user

    response = admin_client.get(reverse("admin:auth_user_change", args=[user_obj.id]))

    assert response.status_code == 200
    assert b"date_of_birth" in response.content


@pytest.mark.django_db
def test_profile_has_no_page_of_its_own():
    """Without a separate page there is no delete button for the profile."""
    with pytest.raises(NoReverseMatch):
        reverse("admin:account_profile_changelist")


@pytest.mark.django_db
def test_admin_can_edit_the_profile_through_the_user(admin_client, user):
    user_obj, _ = user
    profile = user_obj.profile

    response = admin_client.post(
        reverse("admin:auth_user_change", args=[user_obj.id]),
        {
            "username": user_obj.username,
            "email": user_obj.email,
            "first_name": "",
            "last_name": "",
            "is_active": "on",
            "date_joined_0": user_obj.date_joined.date().isoformat(),
            "date_joined_1": user_obj.date_joined.time().isoformat(),
            "profile-TOTAL_FORMS": "1",
            "profile-INITIAL_FORMS": "1",
            "profile-MIN_NUM_FORMS": "0",
            "profile-MAX_NUM_FORMS": "1",
            "profile-0-id": str(profile.id),
            "profile-0-user": str(user_obj.id),
            "profile-0-date_of_birth": "1990-01-01",
        },
    )

    assert response.status_code == 302
    profile.refresh_from_db()
    assert profile.date_of_birth.isoformat() == "1990-01-01"


@pytest.mark.django_db
def test_deleting_the_user_still_removes_the_profile(admin_client, user):
    user_obj, _ = user
    profile_id = user_obj.profile.id

    response = admin_client.post(
        reverse("admin:auth_user_delete", args=[user_obj.id]), {"post": "yes"}
    )

    assert response.status_code == 302
    assert not Profile.objects.filter(id=profile_id).exists()
