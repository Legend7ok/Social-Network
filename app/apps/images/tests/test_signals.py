from unittest.mock import patch

import pytest

from apps.images.models import Image


@pytest.mark.django_db
def test_delete_dispatches_artifact_cleanup(image, django_capture_on_commit_callbacks):
    image_id, file_name = image.id, image.image.name

    with patch("apps.images.signals.delete_image_artifacts.delay") as mock_delay:
        with django_capture_on_commit_callbacks(execute=True):
            image.delete()

    mock_delay.assert_called_once_with(image_id, file_name)


@pytest.mark.django_db
def test_delete_does_not_dispatch_before_commit(image):
    with patch("apps.images.signals.delete_image_artifacts.delay") as mock_delay:
        image.delete()

    mock_delay.assert_not_called()


@pytest.mark.django_db
def test_like_increments_total_likes(image, second_user):
    liker, _ = second_user
    image.users_like.add(liker)
    image.refresh_from_db()
    assert image.total_likes == 1


@pytest.mark.django_db
def test_unlike_decrements_total_likes(image, second_user):
    liker, _ = second_user
    image.users_like.add(liker)
    image.users_like.remove(liker)
    image.refresh_from_db()
    assert image.total_likes == 0


@pytest.mark.django_db
def test_remove_when_not_liked_does_not_go_below_zero(image, second_user):
    liker, _ = second_user
    image.users_like.remove(liker)
    image.refresh_from_db()
    assert image.total_likes == 0


@pytest.mark.django_db
def test_liking_for_several_people_at_once_counts_them_all(
    image, second_user, make_user
):
    """One call carries a set, not a single row: the counter used to move by
    one however many likes arrived."""
    liker, _ = second_user
    other, _ = make_user("carol", "carol@example.com", "testpass789")

    image.users_like.add(liker, other)

    image.refresh_from_db()
    assert image.total_likes == 2


@pytest.mark.django_db
def test_liking_from_the_person_side_counts_each_picture(user, image, second_user):
    """The same call can arrive from the other end of the relation, where the
    instance is the person and the set is the pictures."""
    owner, _ = user
    liker, _ = second_user
    second_image = Image.objects.create(
        user=owner, title="Another", url="https://example.com/other.png"
    )

    liker.images_liked.add(image, second_image)

    image.refresh_from_db()
    second_image.refresh_from_db()
    assert image.total_likes == 1
    assert second_image.total_likes == 1


@pytest.mark.django_db
def test_a_leaving_account_takes_its_like_with_it(image, second_user):
    """A cascade clears the like rows without sending the m2m signal, so the
    counter used to keep counting a like nobody had given."""
    liker, _ = second_user
    image.users_like.add(liker)

    liker.delete()

    image.refresh_from_db()
    assert image.total_likes == 0
    assert not image.users_like.exists()


@pytest.mark.django_db
def test_a_leaving_account_leaves_the_rest_alone(image, second_user, make_user):
    """Only the pictures this person liked, and only by one."""
    liker, _ = second_user
    other, _ = make_user("carol", "carol@example.com", "testpass789")
    image.users_like.add(liker, other)

    liker.delete()

    image.refresh_from_db()
    assert image.total_likes == 1


@pytest.mark.django_db
def test_a_leaving_account_cannot_push_a_counter_below_zero(image, second_user):
    """The counter and the like table can already disagree — that is what this
    whole guard is about — so it must not make matters worse."""
    liker, _ = second_user
    image.users_like.add(liker)
    Image.objects.filter(pk=image.pk).update(total_likes=0)

    liker.delete()

    image.refresh_from_db()
    assert image.total_likes == 0
