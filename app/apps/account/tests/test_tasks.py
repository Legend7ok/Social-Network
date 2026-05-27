import pytest
from unittest.mock import patch
from django.core import mail

from apps.account.tasks import send_welcome_email


@pytest.mark.django_db
def test_send_welcome_email_sends_correct_email(user):
    user_obj, _ = user
    send_welcome_email(user_obj.id)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Welcome to Social Network"
    assert mail.outbox[0].to == [user_obj.email]


@pytest.mark.django_db
def test_send_welcome_email_silently_ignores_missing_user(db):
    send_welcome_email(9999)


@pytest.mark.django_db
def test_send_welcome_email_raises_on_mail_error(user):
    user_obj, _ = user
    with patch("apps.account.tasks.send_mail", side_effect=Exception("SMTP error")):
        with pytest.raises(Exception, match="SMTP error"):
            send_welcome_email(user_obj.id)
