from django.db import transaction
from django.db.models import F
from django.db.models.signals import m2m_changed, post_delete
from django.dispatch import receiver

from .models import Image
from .tasks import delete_image_artifacts


@receiver(post_delete, sender=Image, dispatch_uid="images_cleanup_artifacts")
def cleanup_image_artifacts(sender, instance, **kwargs):
    # Hooked to the model rather than the view so admin deletions, cascades and
    # the oversized-download discard clean up after themselves too. The file
    # name has to be captured now; after the commit the instance is all we have.
    file_name = instance.image.name
    image_id = instance.pk
    transaction.on_commit(lambda: delete_image_artifacts.delay(image_id, file_name))


@receiver(
    m2m_changed,
    sender=Image.users_like.through,
    dispatch_uid="images_users_like_changed",
)
def users_like_changed(sender, instance, action, **kwargs):
    if action == "post_add":
        Image.objects.filter(pk=instance.pk).update(total_likes=F("total_likes") + 1)
    elif action == "post_remove":
        Image.objects.filter(pk=instance.pk, total_likes__gt=0).update(
            total_likes=F("total_likes") - 1
        )
