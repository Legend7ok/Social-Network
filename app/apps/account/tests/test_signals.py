import pytest
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile

from conftest import MINIMAL_PNG


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
