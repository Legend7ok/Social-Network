from django.core.cache import cache
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.actions.models import Action

from .models import Profile
from .tasks import generate_avatar_thumbnails


@receiver(post_save, sender=Action)
def invalidate_dashboard_cache(sender, instance, created, **kwargs):
    if not created or not hasattr(instance.user, "profile"):
        return
    for profile in instance.user.profile.followers.all():
        cache.delete(f"home_{profile.user_id}")


@receiver(pre_save, sender=Profile)
def remember_old_photo(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_photo = None
        return
    try:
        instance._old_photo = sender.objects.get(pk=instance.pk).photo.name
    except sender.DoesNotExist:
        instance._old_photo = None


@receiver(post_save, sender=Profile)
def generate_avatar_on_photo_change(sender, instance, **kwargs):
    if instance.photo and instance.photo.name != instance._old_photo:
        generate_avatar_thumbnails.delay(instance.id)
