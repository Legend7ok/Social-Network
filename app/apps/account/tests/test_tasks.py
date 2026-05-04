import pytest
from unittest.mock import patch

from apps.account.tasks import send_welcome_email


@pytest.mark.django_db
def test_send_welcome_email_sends_correct_email(user):
    user_obj, _ = user
    with patch("apps.account.tasks.send_mail") as mock_send:
        send_welcome_email(user_obj.id)

    mock_send.assert_called_once()
    _, kwargs = mock_send.call_args
    assert kwargs["subject"] == "Welcome to Social Network"
    assert kwargs["recipient_list"] == [user_obj.email]


@pytest.mark.django_db
def test_send_welcome_email_silently_ignores_missing_user(db):
    send_welcome_email(9999)
