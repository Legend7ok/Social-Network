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
def test_image_like_nonexistent_returns_404(auth_client):
    url = reverse("image-like", args=[9999])
    response = auth_client.post(url, {"action": "like"}, format="json")
    assert response.status_code == 404


@pytest.mark.django_db
def test_image_like_invalid_action_returns_400(auth_client, image):
    url = reverse("image-like", args=[image.pk])
    response = auth_client.post(url, {"action": "invalid"}, format="json")
    assert response.status_code == 400
