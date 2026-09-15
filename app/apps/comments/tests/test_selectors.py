import pytest
from django.utils import timezone

from apps.comments.models import Comment
from apps.comments.selectors import (
    PREVIEW_REPLIES,
    attach_replies,
    image_comments,
    thread_replies,
)
from apps.images.models import Image


def write(image, author, body="Nice one", parent=None):
    return Comment.objects.create(image=image, user=author, body=body, parent=parent)


def take_down(comment):
    comment.removed_at = timezone.now()
    comment.save(update_fields=["removed_at"])
    return comment


@pytest.mark.django_db
def test_the_newest_comment_comes_first(image, user):
    author, _ = user
    write(image, author, body="First")
    write(image, author, body="Second")

    assert [c.body for c in image_comments(image)] == ["Second", "First"]


@pytest.mark.django_db
def test_replies_and_other_pictures_stay_out_of_the_list(image, user, second_user):
    author, _ = user
    stranger, _ = second_user
    root = write(image, author, body="Root")
    write(image, stranger, body="A reply", parent=root)
    elsewhere = Image.objects.create(
        user=stranger, title="Another", url="https://example.com/other.png"
    )
    write(elsewhere, stranger, body="Somewhere else")

    assert [c.body for c in image_comments(image)] == ["Root"]


@pytest.mark.django_db
def test_a_comment_taken_down_leaves_the_list(image, user):
    author, _ = user
    take_down(write(image, author, body="Gone"))

    assert list(image_comments(image)) == []


@pytest.mark.django_db
def test_a_taken_down_comment_stays_while_its_answers_are_readable(
    image, user, second_user
):
    """Its answers are still someone's words, and answers under nothing read
    as a bug - the template shows a tombstone in its place."""
    author, _ = user
    answerer, _ = second_user
    root = take_down(write(image, author, body="Gone"))
    write(image, answerer, body="Still here", parent=root)

    assert [c.body for c in image_comments(image)] == ["Gone"]


@pytest.mark.django_db
def test_a_taken_down_comment_leaves_once_its_answers_are_gone_too(
    image, user, second_user
):
    author, _ = user
    answerer, _ = second_user
    root = take_down(write(image, author, body="Gone"))
    take_down(write(image, answerer, body="Also gone", parent=root))

    assert list(image_comments(image)) == []


@pytest.mark.django_db
def test_the_first_answers_hang_on_the_comment_oldest_first(
    image, user, second_user, django_assert_num_queries
):
    author, _ = user
    answerer, _ = second_user
    root = write(image, author, body="Root")
    for n in range(PREVIEW_REPLIES + 3):
        write(image, answerer, body=f"Reply {n}", parent=root)

    roots = list(image_comments(image))
    with django_assert_num_queries(1):
        attach_replies(roots)

    assert [r.body for r in roots[0].preview_replies] == ["Reply 0", "Reply 1"]
    assert roots[0].more_replies == 3


@pytest.mark.django_db
def test_one_query_serves_every_comment_of_the_page(
    image, user, second_user, django_assert_num_queries
):
    """The promise of the whole selector: a page of ten conversations costs
    what a page of one costs."""
    author, _ = user
    answerer, _ = second_user
    for n in range(10):
        write(image, answerer, body="An answer", parent=write(image, author))

    roots = list(image_comments(image))
    with django_assert_num_queries(1):
        attach_replies(roots)

    assert all(len(root.preview_replies) == 1 for root in roots)


@pytest.mark.django_db
def test_answers_taken_down_are_neither_shown_nor_counted(image, user, second_user):
    author, _ = user
    answerer, _ = second_user
    root = write(image, author, body="Root")
    write(image, answerer, body="Readable", parent=root)
    take_down(write(image, answerer, body="Gone", parent=root))

    roots = list(image_comments(image))
    attach_replies(roots)

    assert [r.body for r in roots[0].preview_replies] == ["Readable"]
    assert roots[0].more_replies == 0


@pytest.mark.django_db
def test_a_comment_without_answers_gets_an_empty_thread(image, user):
    author, _ = user
    write(image, author, body="Alone")

    roots = list(image_comments(image))
    attach_replies(roots)

    assert roots[0].preview_replies == []
    assert roots[0].more_replies == 0


@pytest.mark.django_db
def test_the_whole_thread_reads_oldest_first(image, user, second_user):
    author, _ = user
    answerer, _ = second_user
    root = write(image, author)
    write(image, answerer, body="First", parent=root)
    write(image, answerer, body="Second", parent=root)
    take_down(write(image, answerer, body="Gone", parent=root))

    assert [r.body for r in thread_replies(root)] == ["First", "Second"]
