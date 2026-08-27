"""The feed keeps itself honest: an action taken back is an entry taken down.

Hooked to the models rather than to the views, so an unfollow from the admin
site or any other path leaves the feed just as correct as the button does.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import m2m_changed, post_delete
from django.dispatch import receiver

from apps.account.models import Contact, Profile
from apps.images.models import Image

from .models import Action

User = get_user_model()


@receiver(
    m2m_changed,
    sender=Image.users_like.through,
    dispatch_uid="actions_drop_entries_of_undone_likes",
)
def drop_entries_of_undone_likes(sender, instance, action, reverse, pk_set, **kwargs):
    if action != "post_remove" or not pk_set:
        return

    entries = Action.objects.filter(
        verb=Action.Verb.LIKED_IMAGE,
        target_ct=ContentType.objects.get_for_model(Image),
    )
    if reverse:
        # instance is the person, pk_set the pictures they stopped liking
        entries.filter(user=instance, target_id__in=pk_set).delete()
    else:
        entries.filter(user_id__in=pk_set, target_id=instance.pk).delete()


@receiver(
    post_delete, sender=Contact, dispatch_uid="actions_drop_entry_of_undone_follow"
)
def drop_entry_of_undone_follow(sender, instance, **kwargs):
    # Both people are named by id through a subquery rather than fetched: this
    # also fires while a whole account is being deleted, and by then the rows
    # this row pointed at may be gone. Nothing found then is the right answer —
    # the entries of a deleted account go with it anyway.
    Action.objects.filter(
        user__profile__id=instance.user_from_id,
        verb=Action.Verb.FOLLOWED_USER,
        target_ct=ContentType.objects.get_for_model(User),
        target_id__in=Profile.objects.filter(pk=instance.user_to_id).values("user_id"),
    ).delete()
