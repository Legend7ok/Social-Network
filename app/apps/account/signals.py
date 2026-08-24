from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.actions.models import Action

from .cache import feed_cache_key
from .models import Profile
from .tasks import generate_avatar_thumbnails

User = get_user_model()


@receiver(post_save, sender=User, dispatch_uid="account_create_profile")
def create_profile(sender, instance, created, raw=False, **kwargs):
    """Single guarantee that every user has a profile, whatever created them:
    registration, createsuperuser, social auth or the admin site."""
    if not created or raw:
        return
    Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=Action, dispatch_uid="account_invalidate_dashboard_cache")
def invalidate_dashboard_cache(sender, instance, created, **kwargs):
    if not created:
        return
    for profile in instance.user.profile.followers.all():
        cache.delete(feed_cache_key(profile.user_id))


@receiver(pre_save, sender=Profile, dispatch_uid="account_remember_old_photo")
def remember_old_photo(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_photo = None
        return
    try:
        instance._old_photo = sender.objects.get(pk=instance.pk).photo.name
    except sender.DoesNotExist:
        instance._old_photo = None


@receiver(
    post_save, sender=Profile, dispatch_uid="account_generate_avatar_on_photo_change"
)
def generate_avatar_on_photo_change(sender, instance, **kwargs):
    if instance.photo and instance.photo.name != instance._old_photo:
        transaction.on_commit(lambda: generate_avatar_thumbnails.delay(instance.id))
