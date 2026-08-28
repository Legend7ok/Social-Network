import pytest

from apps.account.models import Contact
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


# ─── entries of undone actions ────────────────────────────────────────────────


@pytest.mark.django_db
def test_taking_a_like_back_takes_its_entry_down(user, second_user, image):
    liker, _ = user
    author, _ = second_user
    image.user = author
    image.save()
    image.users_like.add(liker)
    create_action(liker, Action.Verb.LIKED_IMAGE, image)

    image.users_like.remove(liker)

    assert not Action.objects.filter(verb=Action.Verb.LIKED_IMAGE).exists()


@pytest.mark.django_db
def test_taking_a_like_back_leaves_other_entries_alone(user, second_user, image):
    liker, _ = user
    other, _ = second_user
    image.users_like.add(liker, other)
    create_action(liker, Action.Verb.LIKED_IMAGE, image)
    create_action(other, Action.Verb.LIKED_IMAGE, image)

    image.users_like.remove(liker)

    assert Action.objects.filter(user=other, verb=Action.Verb.LIKED_IMAGE).exists()
    assert not Action.objects.filter(user=liker, verb=Action.Verb.LIKED_IMAGE).exists()


@pytest.mark.django_db
def test_the_same_like_undone_from_the_person_side_is_dropped_too(
    user, second_user, image
):
    """Both ends of the relation are honoured: the same removal reaches the
    signal the other way round when it starts from the person."""
    liker, _ = user
    author, _ = second_user
    image.user = author
    image.save()
    liker.images_liked.add(image)
    create_action(liker, Action.Verb.LIKED_IMAGE, image)

    liker.images_liked.remove(image)

    assert not Action.objects.filter(verb=Action.Verb.LIKED_IMAGE).exists()


@pytest.mark.django_db
def test_unfollowing_takes_its_entry_down(user, second_user):
    follower, _ = user
    followed, _ = second_user
    contact = Contact.objects.create(
        user_from=follower.profile, user_to=followed.profile
    )
    create_action(follower, Action.Verb.FOLLOWED_USER, followed)

    contact.delete()

    assert not Action.objects.filter(verb=Action.Verb.FOLLOWED_USER).exists()


@pytest.mark.django_db
def test_deleting_a_person_takes_the_entries_aimed_at_them_down(
    user, second_user, make_user
):
    follower, _ = user
    leaving, _ = second_user
    staying, _ = make_user("carol", "carol@example.com", "testpass789")
    create_action(follower, Action.Verb.FOLLOWED_USER, leaving)
    create_action(follower, Action.Verb.FOLLOWED_USER, staying)

    leaving.delete()

    remaining = Action.objects.filter(verb=Action.Verb.FOLLOWED_USER)
    assert remaining.count() == 1
    assert remaining.first().target == staying


@pytest.mark.django_db
def test_unfollowing_leaves_the_other_direction_alone(user, second_user):
    follower, _ = user
    followed, _ = second_user
    contact = Contact.objects.create(
        user_from=follower.profile, user_to=followed.profile
    )
    Contact.objects.create(user_from=followed.profile, user_to=follower.profile)
    create_action(follower, Action.Verb.FOLLOWED_USER, followed)
    create_action(followed, Action.Verb.FOLLOWED_USER, follower)

    contact.delete()

    assert not Action.objects.filter(user=follower).exists()
    assert Action.objects.filter(user=followed).exists()
