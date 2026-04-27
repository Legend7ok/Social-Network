from django.db.models import F
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from .models import Image


@receiver(m2m_changed, sender=Image.users_like.through)
def users_like_changed(sender, instance, action, **kwargs):
    if action == "post_add":
        Image.objects.filter(pk=instance.pk).update(total_likes=F("total_likes") + 1)
    elif action == "post_remove":
        Image.objects.filter(pk=instance.pk).update(total_likes=F("total_likes") - 1)
