import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.actions.models import Action
from apps.comments.models import Comment

pytestmark = pytest.mark.django_db


def add_url(image):
    return reverse("comments:create", args=[image.id])


def comment_entries():
    return Action.objects.filter(verb=Action.Verb.COMMENTED_IMAGE)


def test_a_comment_is_announced_and_points_at_itself(client, image, second_user):
    """The entry points at the comment, not at the picture, so the card can
    print what was said and so taking it down can find its own entry."""
    visitor, _ = second_user
    client.force_login(visitor)

    client.post(add_url(image), {"body": "Lovely light"})

    entry = comment_entries().get()
    comment = Comment.objects.get()
    assert entry.user == visitor
    assert entry.target_ct == ContentType.objects.get_for_model(Comment)
    assert entry.target_id == comment.id


def test_an_answer_is_not_announced(client, image, user, second_user):
    author, _ = user
    answerer, _ = second_user
    root = Comment.objects.create(image=image, user=author, body="Root")
    client.force_login(answerer)

    client.post(add_url(image), {"body": "Thanks", "parent": root.id})

    assert comment_entries().count() == 0


def test_commenting_on_your_own_picture_is_not_announced(client, image, user):
    author, _ = user
    client.force_login(author)

    client.post(add_url(image), {"body": "My own words"})

    assert comment_entries().count() == 0


def test_two_comments_in_a_row_are_two_entries(client, image, second_user):
    """Entries of the same kind within a minute are usually collapsed into
    one; pointing at the comment rather than the picture is what keeps two
    comments under one picture from swallowing each other."""
    visitor, _ = second_user
    client.force_login(visitor)

    client.post(add_url(image), {"body": "First thought"})
    client.post(add_url(image), {"body": "Second thought"})

    assert comment_entries().count() == 2
