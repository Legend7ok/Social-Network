import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from sorl.thumbnail import get_thumbnail

from .models import Profile
from .display import display_name

User = get_user_model()

logger = logging.getLogger(__name__)


@shared_task
def send_welcome_email(user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning("send_welcome_email: user %s not found, skipping", user_id)
        return
    greeting = display_name(user)
    try:
        send_mail(
            subject="Welcome to Social Network",
            message=f"Hi {greeting}, thanks for joining!",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
    except Exception as exc:
        logger.error(
            "send_welcome_email: failed to send email to user %s: %s", user_id, exc
        )
        raise


@shared_task(autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def generate_avatar_thumbnails(profile_id):
    try:
        profile = Profile.objects.get(id=profile_id)
    except Profile.DoesNotExist:
        logger.warning(
            "generate_avatar_thumbnails: profile %s not found, skipping", profile_id
        )
        return
    if not profile.photo:
        logger.warning(
            "generate_avatar_thumbnails: profile %s has no photo, skipping", profile_id
        )
        return
    thumbs = settings.THUMBNAILS
    get_thumbnail(profile.photo, thumbs["avatar_sm"], crop="center")
    get_thumbnail(profile.photo, thumbs["avatar_md"], crop="center")
    get_thumbnail(profile.photo, thumbs["avatar_lg"], crop="center")
