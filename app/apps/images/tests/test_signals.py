from unittest.mock import patch

import pytest


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
