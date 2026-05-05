import pytest


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
