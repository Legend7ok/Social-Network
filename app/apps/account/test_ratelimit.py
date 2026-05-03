import pytest
from django.core.cache import cache
from django.urls import reverse


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


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
