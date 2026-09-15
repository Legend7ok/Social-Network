import pytest
from django.urls import reverse
from django.utils import timezone

from apps.comments.models import Comment
from apps.images.models import Image

pytestmark = pytest.mark.django_db


def add_url(image):
    return reverse("comments:create", args=[image.id])


def write(image, author, body="Nice one", parent=None):
    return Comment.objects.create(image=image, user=author, body=body, parent=parent)


def signed_in(client, person):
    client.force_login(person)
    return client


def test_a_guest_is_sent_to_the_sign_in_page(client, image):
    response = client.post(add_url(image), {"body": "Hello"})

    assert response.status_code == 302
    assert reverse("login") in response.url
    assert Comment.objects.count() == 0


def test_reading_the_address_is_refused(client, image, user):
    author, _ = user

    response = signed_in(client, author).get(add_url(image))

    assert response.status_code == 405


def test_a_comment_is_written_under_the_picture(client, image, second_user):
    visitor, _ = second_user

    response = signed_in(client, visitor).post(add_url(image), {"body": "Lovely light"})

    comment = Comment.objects.get()
    assert response.status_code == 302
    assert response.url == image.get_absolute_url()
    assert (comment.body, comment.user, comment.image, comment.parent) == (
        "Lovely light",
        visitor,
        image,
        None,
    )


def test_an_answer_hangs_on_the_comment_it_answers(client, image, user, second_user):
    author, _ = user
    answerer, _ = second_user
    root = write(image, author)

    signed_in(client, answerer).post(
        add_url(image), {"body": "Thanks", "parent": root.id}
    )

    assert Comment.objects.get(parent=root).body == "Thanks"


def test_an_answer_to_an_answer_is_not_found(client, image, user, second_user):
    """One level is the shape of the thread, and the page offers no such
    button - a request asking for it was not built by the page."""
    author, _ = user
    answerer, _ = second_user
    reply = write(image, answerer, parent=write(image, author))

    response = signed_in(client, author).post(
        add_url(image), {"body": "Again", "parent": reply.id}
    )

    assert response.status_code == 404
    assert Comment.objects.count() == 2


def test_an_answer_to_a_comment_under_another_picture_is_not_found(
    client, image, user, second_user
):
    author, _ = user
    stranger, _ = second_user
    elsewhere = Image.objects.create(
        user=stranger, title="Another", url="https://example.com/other.png"
    )
    root = write(elsewhere, stranger)

    response = signed_in(client, author).post(
        add_url(image), {"body": "Wrong page", "parent": root.id}
    )

    assert response.status_code == 404
    assert Comment.objects.count() == 1


def test_an_answer_to_a_comment_taken_down_is_not_found(client, image, user):
    """Its words are gone from the page; answering them would put a reply
    under a tombstone."""
    author, _ = user
    root = write(image, author)
    root.removed_at = timezone.now()
    root.save(update_fields=["removed_at"])

    response = signed_in(client, author).post(
        add_url(image), {"body": "Hello?", "parent": root.id}
    )

    assert response.status_code == 404


def test_a_made_up_parent_is_not_found(client, image, user):
    author, _ = user

    response = signed_in(client, author).post(
        add_url(image), {"body": "Hello", "parent": "not-a-number"}
    )

    assert response.status_code == 404


def test_an_empty_comment_is_not_written(client, image, user):
    author, _ = user

    response = signed_in(client, author).post(add_url(image), {"body": "   "})

    assert response.status_code == 302
    assert Comment.objects.count() == 0


def test_a_comment_under_a_missing_picture_is_not_found(client, image, user):
    author, _ = user
    missing = image.id
    image.delete()

    response = signed_in(client, author).post(
        reverse("comments:create", args=[missing]), {"body": "Hello"}
    )

    assert response.status_code == 404
