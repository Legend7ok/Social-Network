from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.db.models.signals import m2m_changed, post_delete, pre_delete
from django.dispatch import receiver

from .models import Image
from .tasks import delete_image_artifacts

User = get_user_model()


@receiver(post_delete, sender=Image, dispatch_uid="images_cleanup_artifacts")
def cleanup_image_artifacts(sender, instance, **kwargs):
    # Hooked to the model rather than the view so admin deletions, cascades and
    # the oversized-download discard clean up after themselves too. The file
    # name has to be captured now; after the commit the instance is all we have.
    file_name = instance.image.name
    image_id = instance.pk
    transaction.on_commit(lambda: delete_image_artifacts.delay(image_id, file_name))


@receiver(
    pre_delete, sender=User, dispatch_uid="images_take_back_the_likes_of_a_leaver"
)
def take_back_the_likes_of_a_leaver(sender, instance, **kwargs):
    """Give back the likes of someone who is leaving.

    Deleting an account clears its rows from the like table by cascade, and a
    cascade sends no m2m signal — so the counter below never heard about it and
    stayed too high forever. The pictures then claimed likes nobody had given,
    and the ranking sorts by exactly that number.

    Before the delete, not after: once it has run, there is nothing left to
    tell us what this person liked.
    """
    Image.objects.filter(users_like=instance).update(
        total_likes=Greatest(F("total_likes") - 1, Value(0))
    )


@receiver(
    m2m_changed,
    sender=Image.users_like.through,
    dispatch_uid="images_users_like_changed",
)
def users_like_changed(sender, instance, action, reverse, pk_set, **kwargs):
    """Keep the counter level with the like table.

    One call can carry several likes at once, and it can arrive from either
    end of the relation, so neither the pictures nor the step can be assumed:
    liking one picture on behalf of five people moves that picture by five,
    while liking five pictures on behalf of one person moves each by one.
    """
    if action not in ("post_add", "post_remove") or not pk_set:
        return

    if reverse:
        # instance is the person, pk_set the pictures they just (un)liked
        images = Image.objects.filter(pk__in=pk_set)
        step = 1
    else:
        images = Image.objects.filter(pk=instance.pk)
        step = len(pk_set)

    if action == "post_add":
        images.update(total_likes=F("total_likes") + step)
    else:
        # The column refuses to go negative, and it can already sit lower than
        # the rows being taken away — that is the drift this whole guard exists
        # for — so the subtraction stops at zero rather than failing.
        images.update(total_likes=Greatest(F("total_likes") - step, Value(0)))
