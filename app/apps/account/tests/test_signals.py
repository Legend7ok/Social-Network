import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.account.models import Profile
from conftest import MINIMAL_PNG


@pytest.mark.django_db
def test_profile_created_for_any_new_user():
    """createsuperuser and the admin site never went through the registration
    view, which is how users without a profile appeared in the first place."""
    user_obj = get_user_model().objects.create_superuser(
        username="root", email="root@example.com", password="rootpass"
    )
    assert Profile.objects.filter(user=user_obj).exists()


@pytest.mark.django_db
def test_saving_an_existing_user_keeps_a_single_profile(user):
    user_obj, _ = user
    user_obj.first_name = "Alice"
    user_obj.save()

    assert Profile.objects.filter(user=user_obj).count() == 1


@pytest.mark.django_db
def test_avatar_thumbnails_dispatched_on_photo_change(
    user, django_capture_on_commit_callbacks
):
    user_obj, _ = user
    profile = user_obj.profile
    with patch("apps.account.signals.generate_avatar_thumbnails.delay") as mock_delay:
        with django_capture_on_commit_callbacks(execute=True):
            profile.photo = SimpleUploadedFile(
                "ava.png", MINIMAL_PNG, content_type="image/png"
            )
            profile.save()
    mock_delay.assert_called_once_with(profile.id)


@pytest.mark.django_db
def test_avatar_thumbnails_not_dispatched_without_photo_change(user):
    user_obj, _ = user
    profile = user_obj.profile  # created without a photo
    with patch("apps.account.signals.generate_avatar_thumbnails.delay") as mock_delay:
        profile.save()
    mock_delay.assert_not_called()
