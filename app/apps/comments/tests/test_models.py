import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.comments.models import Comment
from apps.images.models import Image


def write(image, author, body="Nice one", parent=None):
    return Comment.objects.create(image=image, user=author, body=body, parent=parent)


@pytest.mark.django_db
def test_a_reply_to_a_comment_is_accepted(image, user, second_user):
    author, _ = user
    answerer, _ = second_user
    root = write(image, author)

    reply = Comment(image=image, user=answerer, body="Thanks", parent=root)
    reply.full_clean()


@pytest.mark.django_db
def test_a_reply_to_a_reply_is_refused(image, user, second_user):
    """One level is the whole shape of the thread: without this the fourth
    answer in a row would sit four steps to the right of the picture."""
    author, _ = user
    answerer, _ = second_user
    reply = write(image, answerer, parent=write(image, author))

    with pytest.raises(ValidationError):
        Comment(image=image, user=author, body="Again", parent=reply).full_clean()


@pytest.mark.django_db
def test_a_reply_under_another_picture_is_refused(image, user, second_user):
    """The parent carries a picture of its own, so a mismatched pair would
    show the same answer under two different pictures - or under none."""
    author, _ = user
    stranger, _ = second_user
    elsewhere = Image.objects.create(
        user=stranger, title="Another", url="https://example.com/other.png"
    )
    root = write(elsewhere, stranger)

    with pytest.raises(ValidationError):
        Comment(image=image, user=author, body="Wrong page", parent=root).full_clean()


@pytest.mark.django_db
def test_taken_down_comments_leave_only_the_filtered_set(image, user):
    author, _ = user
    write(image, author, body="Stays")
    gone = write(image, author, body="Goes")
    gone.removed_at = timezone.now()
    gone.save(update_fields=["removed_at"])

    assert Comment.objects.count() == 2
    assert [c.body for c in Comment.objects.visible()] == ["Stays"]


@pytest.mark.django_db
def test_an_empty_comment_is_refused_by_the_database(image, user):
    """The form trims and refuses blanks, but it is not the only way in:
    the shell, the admin and a data migration all write rows too."""
    author, _ = user

    with pytest.raises(IntegrityError):
        write(image, author, body="")


@pytest.mark.django_db
def test_a_deleted_comment_takes_its_replies_with_it(image, user, second_user):
    author, _ = user
    answerer, _ = second_user
    root = write(image, author)
    write(image, answerer, body="Thanks", parent=root)

    root.delete()

    assert Comment.objects.count() == 0
