import pytest
from django.urls import reverse


# ─── ImageLikeView ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_image_like_unauthenticated(api_client, image):
    url = reverse("image-like", args=[image.pk])
    response = api_client.post(url, {"action": "like"}, format="json")
    assert response.status_code == 403


@pytest.mark.django_db
def test_image_like_adds_user(auth_client, user, image):
    user_obj, _ = user
    url = reverse("image-like", args=[image.pk])
    response = auth_client.post(url, {"action": "like"}, format="json")
    assert response.status_code == 200
    assert response.data == {"status": "ok"}
    assert image.users_like.filter(pk=user_obj.pk).exists()


@pytest.mark.django_db
def test_image_like_removes_user(auth_client, user, image):
    user_obj, _ = user
    image.users_like.add(user_obj)
    url = reverse("image-like", args=[image.pk])
    response = auth_client.post(url, {"action": "unlike"}, format="json")
    assert response.status_code == 200
    assert not image.users_like.filter(pk=user_obj.pk).exists()


@pytest.mark.django_db
def test_image_like_writes_a_feed_entry_for_someone_elses_picture(
    auth_client, user, second_user, image
):
    from apps.actions.models import Action

    user_obj, _ = user
    other, _ = second_user
    image.user = other
    image.save()

    auth_client.post(
        reverse("image-like", args=[image.pk]), {"action": "like"}, format="json"
    )

    assert Action.objects.filter(
        user=user_obj, verb=Action.Verb.LIKED_IMAGE, target_id=image.pk
    ).exists()


@pytest.mark.django_db
def test_image_like_writes_no_feed_entry_for_your_own_picture(auth_client, user, image):
    """The like itself stands; only the announcement is dropped — followers
    have already seen this picture as an upload."""
    from apps.actions.models import Action

    user_obj, _ = user

    auth_client.post(
        reverse("image-like", args=[image.pk]), {"action": "like"}, format="json"
    )

    assert image.users_like.filter(pk=user_obj.pk).exists()
    assert not Action.objects.filter(verb=Action.Verb.LIKED_IMAGE).exists()


@pytest.mark.django_db
def test_image_like_nonexistent_returns_404(auth_client):
    url = reverse("image-like", args=[9999])
    response = auth_client.post(url, {"action": "like"}, format="json")
    assert response.status_code == 404


@pytest.mark.django_db
def test_image_like_invalid_action_returns_400(auth_client, image):
    url = reverse("image-like", args=[image.pk])
    response = auth_client.post(url, {"action": "invalid"}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_image_like_throttled_after_limit(auth_client, image, monkeypatch):
    from core.throttles import LikeRateThrottle

    monkeypatch.setattr(LikeRateThrottle, "rate", "1/min", raising=False)
    url = reverse("image-like", args=[image.pk])
    auth_client.post(url, {"action": "like"}, format="json")
    response = auth_client.post(url, {"action": "like"}, format="json")
    assert response.status_code == 429
