import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.account.models import Contact
from apps.actions.models import Action


@pytest.mark.django_db
def test_dashboard_cache_miss_populates_cache(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    assert cache.get(f"dashboard_{user_obj.id}") is None
    client.get(reverse("dashboard"))
    assert cache.get(f"dashboard_{user_obj.id}") is not None


@pytest.mark.django_db
def test_dashboard_cache_invalidated_on_new_action(client, user, second_user):
    alice, alice_password = user
    bob, bob_password = second_user

    Contact.objects.create(user_from=bob.profile, user_to=alice.profile)

    client.login(username=bob.username, password=bob_password)
    client.get(reverse("dashboard"))
    assert cache.get(f"dashboard_{bob.id}") is not None

    Action.objects.create(user=alice, verb="liked an image")

    assert cache.get(f"dashboard_{bob.id}") is None


@pytest.mark.django_db
def test_dashboard_cache_not_invalidated_for_non_followers(client, user, second_user):
    alice, alice_password = user
    bob, bob_password = second_user

    client.login(username=alice.username, password=alice_password)
    client.get(reverse("dashboard"))
    assert cache.get(f"dashboard_{alice.id}") is not None

    Action.objects.create(user=bob, verb="liked an image")

    assert cache.get(f"dashboard_{alice.id}") is not None
