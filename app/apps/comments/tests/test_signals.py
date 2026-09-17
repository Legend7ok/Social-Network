import pytest
from django.utils import timezone

from apps.comments.models import Comment
from apps.images.models import Image


def write(image, author, body="Nice one", parent=None):
    return Comment.objects.create(image=image, user=author, body=body, parent=parent)


def counter(image):
    return Image.objects.values_list("total_comments", flat=True).get(pk=image.pk)


def take_down(comment, by=None):
    comment.removed_at = timezone.now()
    comment.removed_by = by
    comment.save(update_fields=["removed_at", "removed_by"])


@pytest.mark.django_db
def test_a_new_comment_asks_nothing_of_the_table_before_it_is_written(
    image, user, django_assert_max_num_queries
):
    """A row about to be inserted has no stored state to compare against. The
    second half checks the check: saving a row that exists does read it, so a
    match on nothing cannot pass for the first half."""
    author, _ = user

    def reads_stored_state(queries):
        return any(
            query["sql"].startswith('SELECT "comments_comment"."removed_at"')
            for query in queries.captured_queries
        )

    with django_assert_max_num_queries(10) as on_create:
        comment = write(image, author)
    with django_assert_max_num_queries(10) as on_save:
        comment.save()

    assert not reads_stored_state(on_create)
    assert reads_stored_state(on_save)


@pytest.mark.django_db
def test_a_comment_and_a_reply_both_count(image, user, second_user):
    """The number under a picture is the whole conversation, answers and all -
    that is what the heading over the block promises."""
    author, _ = user
    answerer, _ = second_user
    root = write(image, author)
    write(image, answerer, body="Thanks", parent=root)

    assert counter(image) == 2


@pytest.mark.django_db
def test_taking_a_comment_down_lowers_the_counter(image, user):
    author, _ = user
    comment = write(image, author)

    take_down(comment, by=author)

    assert counter(image) == 0


@pytest.mark.django_db
def test_saving_a_hidden_comment_again_changes_nothing(image, user):
    """Anything may save the row a second time - the admin, a later field.
    Counting the same removal twice is how a counter goes wrong for good."""
    author, _ = user
    comment = write(image, author)
    take_down(comment, by=author)

    comment.body = "Edited by a moderator"
    comment.save()

    assert counter(image) == 0


@pytest.mark.django_db
def test_putting_a_comment_back_raises_the_counter(image, user):
    author, _ = user
    comment = write(image, author)
    take_down(comment, by=author)

    comment.removed_at = None
    comment.removed_by = None
    comment.save(update_fields=["removed_at", "removed_by"])

    assert counter(image) == 1


@pytest.mark.django_db
def test_deleting_a_comment_for_good_lowers_the_counter(image, user):
    author, _ = user

    write(image, author).delete()

    assert counter(image) == 0


@pytest.mark.django_db
def test_deleting_an_already_hidden_comment_leaves_the_counter_alone(image, user):
    """It was taken off the number when it was hidden; doing it again would
    take away a comment that is still on the page."""
    author, _ = user
    staying = write(image, author, body="Stays")
    gone = write(image, author, body="Goes")
    take_down(gone, by=author)

    gone.delete()

    assert counter(image) == 1
    assert Comment.objects.visible().count() == 1
    assert staying.pk is not None


@pytest.mark.django_db
def test_a_leaving_account_takes_its_comments_off_the_counter(image, second_user):
    """Their rows go by cascade, and unlike the like table this one is a plain
    foreign key, so the signal above hears about every one of them."""
    guest, _ = second_user
    write(image, guest)

    guest.delete()

    assert counter(image) == 0


@pytest.mark.django_db
def test_deleting_a_picture_never_touches_its_own_counter(
    image, user, second_user, django_assert_max_num_queries
):
    author, _ = user
    answerer, _ = second_user
    write(image, answerer, parent=write(image, author))

    with django_assert_max_num_queries(50) as queries:
        image.delete()

    assert not any(
        "total_comments" in query["sql"] for query in queries.captured_queries
    )
    assert Comment.objects.count() == 0
