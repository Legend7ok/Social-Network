"""The feed keeps itself honest: an action taken back is an entry taken down.

Hooked to the models rather than to the views, so an unfollow from the admin
site or any other path leaves the feed just as correct as the button does.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from apps.account.models import Contact, Profile
from apps.comments.models import Comment
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


@receiver(
    post_delete, sender=User, dispatch_uid="actions_drop_entries_aimed_at_a_gone_person"
)
def drop_entries_aimed_at_a_gone_person(sender, instance, **kwargs):
    # A target is reached without a foreign key, so nothing cascades to it:
    # what this person did leaves with them, what was done to them stays and
    # draws a card pointing at nobody.
    Action.objects.filter(
        target_ct=ContentType.objects.get_for_model(User),
        target_id=instance.pk,
    ).delete()


@receiver(
    post_save, sender=Comment, dispatch_uid="actions_drop_entry_of_a_hidden_comment"
)
def drop_entry_of_a_hidden_comment(sender, instance, raw=False, **kwargs):
    if raw or instance.removed_at is None:
        return
    _entries_about_comment(instance.pk).delete()


@receiver(
    post_delete, sender=Comment, dispatch_uid="actions_drop_entry_of_a_gone_comment"
)
def drop_entry_of_a_gone_comment(sender, instance, **kwargs):
    # Asked even when the comment was already hidden: the hiding may have come
    # through a bulk update that no signal heard, and the entry is still there.
    _entries_about_comment(instance.pk).delete()


def _entries_about_comment(comment_id):
    return Action.objects.filter(
        target_ct=ContentType.objects.get_for_model(Comment),
        target_id=comment_id,
    )
