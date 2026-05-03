from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.actions.models import Action


@receiver(post_save, sender=Action)
def invalidate_dashboard_cache(sender, instance, created, **kwargs):
    if not created:
        return
    for profile in instance.user.profile.followers.all():
        cache.delete(f"dashboard_{profile.user_id}")
