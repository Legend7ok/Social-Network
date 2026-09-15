import pytest
from django.urls import reverse
from django.utils import timezone

from apps.comments.models import Comment
from apps.images.models import Image

pytestmark = pytest.mark.django_db


def add_url(image):
    return reverse("comments:create", args=[image.id])


def remove_url(comment):
    return reverse("comments:remove", args=[comment.id])


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


def test_the_writer_takes_their_own_comment_down(client, image, second_user):
    visitor, _ = second_user
    comment = write(image, visitor)

    response = signed_in(client, visitor).post(remove_url(comment))

    comment.refresh_from_db()
    image.refresh_from_db()
    assert response.status_code == 302
    assert comment.removed_at is not None
    assert comment.removed_by == visitor
    assert image.total_comments == 0


def test_the_owner_of_the_picture_takes_someone_down(client, image, user, second_user):
    """Whoever the picture belongs to answers for what sits under it."""
    owner, _ = user
    visitor, _ = second_user
    comment = write(image, visitor)

    signed_in(client, owner).post(remove_url(comment))

    comment.refresh_from_db()
    assert comment.removed_by == owner


def test_a_bystander_is_not_allowed_near_it(client, image, second_user, make_user):
    visitor, _ = second_user
    bystander, _ = make_user("carol", "carol@example.com", "testpass321")
    comment = write(image, visitor)

    response = signed_in(client, bystander).post(remove_url(comment))

    comment.refresh_from_db()
    assert response.status_code == 404
    assert comment.removed_at is None


def test_a_guest_cannot_take_anything_down(client, image, user):
    author, _ = user
    comment = write(image, author)

    response = client.post(remove_url(comment))

    comment.refresh_from_db()
    assert reverse("login") in response.url
    assert comment.removed_at is None


def test_reading_the_removal_address_is_refused(client, image, user):
    author, _ = user
    comment = write(image, author)

    response = signed_in(client, author).get(remove_url(comment))

    assert response.status_code == 405


def test_pressing_it_twice_keeps_the_first_record(client, image, user, second_user):
    """A second tab or an impatient hand must not rewrite the hour, and the
    owner of the picture must not take the blame for what its writer did."""
    owner, _ = user
    visitor, _ = second_user
    comment = write(image, visitor)
    signed_in(client, visitor).post(remove_url(comment))
    comment.refresh_from_db()
    first_time = comment.removed_at

    signed_in(client, owner).post(remove_url(comment))

    comment.refresh_from_db()
    image.refresh_from_db()
    assert (comment.removed_at, comment.removed_by) == (first_time, visitor)
    assert image.total_comments == 0


def test_an_answer_can_be_taken_down_as_well(client, image, user, second_user):
    author, _ = user
    answerer, _ = second_user
    reply = write(image, answerer, body="Thanks", parent=write(image, author))

    signed_in(client, answerer).post(remove_url(reply))

    reply.refresh_from_db()
    assert reply.removed_at is not None


def test_taking_a_comment_down_leaves_its_answers_readable(
    client, image, user, second_user
):
    author, _ = user
    answerer, _ = second_user
    root = write(image, author)
    reply = write(image, answerer, body="Thanks", parent=root)

    signed_in(client, author).post(remove_url(root))

    reply.refresh_from_db()
    assert reply.removed_at is None
