"""The counter on a picture follows what a reader can actually see.

Hidden rows stay in the table, so the number cannot be "how many rows point
here": it moves when a comment appears, when it is taken down, when it is put
back and when it is deleted for good. Hooked to the model rather than the
views, so the admin site moves it too.
"""

from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.images.models import Image

from .models import Comment


def _move_counter(image_id, up):
    images = Image.objects.filter(pk=image_id)
    if up:
        images.update(total_comments=F("total_comments") + 1)
    else:
        # A counter that drifted low once would otherwise refuse every removal
        # after it: the column cannot hold a negative number.
        images.update(total_comments=Greatest(F("total_comments") - 1, Value(0)))


@receiver(pre_save, sender=Comment, dispatch_uid="comments_remember_what_showed")
def remember_what_showed(sender, instance, **kwargs):
    stored = sender.objects.filter(pk=instance.pk).values_list("removed_at", flat=True)[
        :1
    ]
    instance._was_showing = bool(stored) and stored[0] is None


@receiver(post_save, sender=Comment, dispatch_uid="comments_keep_the_counter_level")
def keep_the_counter_level(sender, instance, raw=False, **kwargs):
    showing = instance.removed_at is None
    if raw or showing == instance._was_showing:
        return
    _move_counter(instance.image_id, up=showing)


@receiver(post_delete, sender=Comment, dispatch_uid="comments_drop_a_gone_comment")
def drop_a_gone_comment(sender, instance, origin=None, **kwargs):
    if instance.removed_at is not None:
        return
    # The picture is on its way out and takes its counter along. Without this a
    # busy picture would pay one update per comment on the way to being deleted.
    if isinstance(origin, Image) and origin.pk == instance.image_id:
        return
    _move_counter(instance.image_id, up=False)
