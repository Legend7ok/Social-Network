import pytest
from django.urls import reverse


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
