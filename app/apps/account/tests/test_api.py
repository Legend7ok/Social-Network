import pytest
from django.urls import reverse

from apps.account.models import Contact


# ─── UserFollowView ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_user_follow_unauthenticated(api_client, second_user):
    target, _ = second_user
    url = reverse("user-follow", args=[target.pk])
    response = api_client.post(url, {"action": "follow"}, format="json")
    assert response.status_code == 403


@pytest.mark.django_db
def test_user_follow_creates_contact(auth_client, user, second_user):
    requester, _ = user
    target, _ = second_user
    url = reverse("user-follow", args=[target.pk])
    response = auth_client.post(url, {"action": "follow"}, format="json")
    assert response.status_code == 200
    assert response.data == {"status": "ok"}
    assert Contact.objects.filter(
        user_from=requester.profile, user_to=target.profile
    ).exists()


@pytest.mark.django_db
def test_user_unfollow_deletes_contact(auth_client, user, second_user):
    requester, _ = user
    target, _ = second_user
    Contact.objects.create(user_from=requester.profile, user_to=target.profile)
    url = reverse("user-follow", args=[target.pk])
    response = auth_client.post(url, {"action": "unfollow"}, format="json")
    assert response.status_code == 200
    assert not Contact.objects.filter(
        user_from=requester.profile, user_to=target.profile
    ).exists()


@pytest.mark.django_db
def test_user_follow_nonexistent_returns_404(auth_client):
    url = reverse("user-follow", args=[9999])
    response = auth_client.post(url, {"action": "follow"}, format="json")
    assert response.status_code == 404


@pytest.mark.django_db
def test_user_follow_invalid_action_returns_400(auth_client, second_user):
    target, _ = second_user
    url = reverse("user-follow", args=[target.pk])
    response = auth_client.post(url, {"action": "invalid"}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_user_follow_throttled_after_limit(auth_client, second_user, monkeypatch):
    from core.throttles import FollowRateThrottle
    monkeypatch.setattr(FollowRateThrottle, "rate", "1/min", raising=False)
    target, _ = second_user
    url = reverse("user-follow", args=[target.pk])
    auth_client.post(url, {"action": "follow"}, format="json")
    response = auth_client.post(url, {"action": "follow"}, format="json")
    assert response.status_code == 429
