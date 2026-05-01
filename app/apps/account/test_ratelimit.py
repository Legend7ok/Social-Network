import pytest
from django.core.cache import cache
from django.urls import reverse


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_user_follow_rate_limit_returns_json_429(client, user, second_user):
    user_obj, password = user
    target_user, _ = second_user
    client.login(username=user_obj.username, password=password)

    url = reverse("user_follow")
    headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

    for _ in range(20):
        response = client.post(
            url, {"id": target_user.id, "action": "follow"}, **headers
        )
        assert response.status_code == 200

    response = client.post(url, {"id": target_user.id, "action": "follow"}, **headers)
    assert response.status_code == 429
    assert response.json() == {"detail": "Too many requests. Try again later."}


@pytest.mark.django_db
def test_register_rate_limit_returns_429(client):
    url = reverse("register")

    for i in range(10):
        response = client.post(
            url,
            {
                "username": f"spammer{i}",
                "first_name": "Spam",
                "email": f"spam{i}@example.com",
                "password": "pass123",
                "password2": "pass123",
            },
        )
        assert response.status_code == 200

    response = client.post(
        url,
        {
            "username": "spammer_final",
            "first_name": "Spam",
            "email": "final@example.com",
            "password": "pass123",
            "password2": "pass123",
        },
    )
    assert response.status_code == 429
