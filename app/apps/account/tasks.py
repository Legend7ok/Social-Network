from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

User = get_user_model()


@shared_task
def send_welcome_email(user_id):
    try:
        user = User.objects.get(id=user_id)
        send_mail(
            subject="Welcome to Social Network",
            message=f"Hi {user.first_name}, thanks for joining!",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
    except Exception:
        pass
