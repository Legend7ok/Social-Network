import pytest

from apps.actions.models import Action
from apps.actions.utils import create_action


@pytest.mark.django_db
def test_create_action_returns_true_and_saves(user):
    user_obj, _ = user
    result = create_action(user_obj, "joined")
    assert result is True
    assert Action.objects.filter(user=user_obj, verb="joined").exists()


@pytest.mark.django_db
def test_create_action_with_target_returns_true(user, image):
    user_obj, _ = user
    result = create_action(user_obj, "bookmarked image", image)
    action = Action.objects.get(user=user_obj, verb="bookmarked image")
    assert result is True
    assert action.target == image


@pytest.mark.django_db
def test_create_action_deduplicates_within_minute(user):
    user_obj, _ = user
    create_action(user_obj, "joined")
    result = create_action(user_obj, "joined")
    assert result is False
    assert Action.objects.filter(user=user_obj, verb="joined").count() == 1


@pytest.mark.django_db
def test_create_action_deduplicates_with_same_target(user, image):
    user_obj, _ = user
    create_action(user_obj, "liked", image)
    result = create_action(user_obj, "liked", image)
    assert result is False
    assert Action.objects.filter(user=user_obj, verb="liked").count() == 1


@pytest.mark.django_db
def test_create_action_different_target_creates_new(user, image, second_user):
    user_obj, _ = user
    second_obj, _ = second_user
    create_action(user_obj, "liked", image)
    result = create_action(user_obj, "liked", second_obj)
    assert result is True
    assert Action.objects.filter(user=user_obj, verb="liked").count() == 2
