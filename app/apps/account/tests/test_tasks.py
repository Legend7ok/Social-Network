import pytest
from unittest.mock import patch
from django.conf import settings
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.account.tasks import generate_avatar_thumbnails, send_welcome_email
from conftest import MINIMAL_PNG


@pytest.mark.django_db
def test_send_welcome_email_sends_correct_email(user):
    user_obj, _ = user
    send_welcome_email(user_obj.id)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Welcome to Social Network"
    assert mail.outbox[0].to == [user_obj.email]


@pytest.mark.django_db
def test_welcome_email_greets_by_username_when_there_is_no_name(user):
    """Registration never asks for a name, so greeting by it left "Hi , "."""
    user_obj, _ = user
    send_welcome_email(user_obj.id)

    assert f"Hi {user_obj.username}," in mail.outbox[0].body


@pytest.mark.django_db
def test_welcome_email_greets_by_name_when_there_is_one(user):
    user_obj, _ = user
    user_obj.first_name = "Alice"
    user_obj.last_name = "Smith"
    user_obj.save()

    send_welcome_email(user_obj.id)

    assert "Hi Alice Smith," in mail.outbox[0].body


@pytest.mark.django_db
def test_send_welcome_email_silently_ignores_missing_user(db):
    send_welcome_email(9999)


@pytest.mark.django_db
def test_send_welcome_email_raises_on_mail_error(user):
    user_obj, _ = user
    with patch("apps.account.tasks.send_mail", side_effect=Exception("SMTP error")):
        with pytest.raises(Exception, match="SMTP error"):
            send_welcome_email(user_obj.id)


@pytest.mark.django_db
def test_generate_avatar_thumbnails_creates_avatar_set(user):
    user_obj, _ = user
    profile = user_obj.profile
    # Attach a photo without triggering the eager signal-driven generation.
    with patch("apps.account.signals.generate_avatar_thumbnails.delay"):
        profile.photo = SimpleUploadedFile(
            "ava.png", MINIMAL_PNG, content_type="image/png"
        )
        profile.save()

    with patch("apps.account.tasks.get_thumbnail") as mock_thumb:
        generate_avatar_thumbnails(profile.id)

    thumbs = settings.THUMBNAILS
    calls = mock_thumb.call_args_list
    assert mock_thumb.call_count == 3
    assert calls[0].args[1] == thumbs["avatar_sm"]
    assert calls[1].args[1] == thumbs["avatar_md"]
    assert calls[2].args[1] == thumbs["avatar_lg"]
    assert all(c.kwargs == {"crop": "center"} for c in calls)


@pytest.mark.django_db
def test_generate_avatar_thumbnails_missing_profile_skips(db):
    with patch("apps.account.tasks.get_thumbnail") as mock_thumb:
        generate_avatar_thumbnails(9999)
    mock_thumb.assert_not_called()


@pytest.mark.django_db
def test_generate_avatar_thumbnails_no_photo_skips(user):
    user_obj, _ = user
    with patch("apps.account.tasks.get_thumbnail") as mock_thumb:
        generate_avatar_thumbnails(user_obj.profile.id)
    mock_thumb.assert_not_called()
