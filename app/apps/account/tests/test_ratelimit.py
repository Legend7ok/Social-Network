import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_register_rate_limit_returns_429(client):
    url = reverse("register")

    for i in range(10):
        response = client.post(
            url,
            {
                "username": f"spammer{i}",
                "email": f"spam{i}@example.com",
                "password": "Str0ngPassphrase!42",
            },
        )
        assert response.status_code == 302
        client.logout()

    response = client.post(
        url,
        {
            "username": "spammer_final",
            "email": "final@example.com",
            "password": "Str0ngPassphrase!42",
        },
    )
    assert response.status_code == 429
