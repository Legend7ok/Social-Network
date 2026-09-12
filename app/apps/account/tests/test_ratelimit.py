import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
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


@pytest.mark.django_db
def test_avatar_upload_rate_limit_returns_429(client, user):
    """Every upload stores a file and sets three thumbnails going, so an
    unbounded one is a way to keep the worker and the bucket busy for free."""
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    url = reverse("profile_photo")

    # A file the form turns away, so the quota is spent without storing
    # anything: the limit is checked before the view looks at the form.
    rejected = {
        "photo": SimpleUploadedFile("a.gif", b"GIF89a", content_type="image/gif")
    }

    for _ in range(30):
        assert client.post(url, rejected).status_code == 302

    assert client.post(url, rejected).status_code == 429
    user_obj.profile.refresh_from_db()
    assert not user_obj.profile.photo
