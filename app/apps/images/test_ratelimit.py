import pytest
from django.core.cache import cache
from django.urls import reverse


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_image_like_rate_limit_returns_json_429(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    url = reverse("images:like")
    headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

    for _ in range(20):
        response = client.post(url, {"id": image.id, "action": "like"}, **headers)
        assert response.status_code == 200

    response = client.post(url, {"id": image.id, "action": "like"}, **headers)
    assert response.status_code == 429
    assert response.json() == {"detail": "Too many requests. Try again later."}


@pytest.mark.django_db
def test_image_create_rate_limit_returns_429(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    url = reverse("images:create")
    data = {"title": "Test", "url": "https://example.com/photo.gif", "description": ""}

    for _ in range(30):
        response = client.post(url, data)
        assert response.status_code == 200

    response = client.post(url, data)
    assert response.status_code == 429
