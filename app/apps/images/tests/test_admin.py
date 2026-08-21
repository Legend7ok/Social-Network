import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.fixture
def admin_login(db, client):
    User = get_user_model()
    User.objects.create_superuser("root", "root@example.com", "adminpass123")
    client.login(username="root", password="adminpass123")
    return client


@pytest.mark.django_db
def test_image_changelist_opens(admin_login, image):
    response = admin_login.get(reverse("admin:images_image_changelist"))

    assert response.status_code == 200
    assert image.title.encode() in response.content


@pytest.mark.django_db
def test_image_change_form_opens(admin_login, image):
    response = admin_login.get(
        reverse("admin:images_image_change", args=[image.id]),
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_image_search_finds_by_author(admin_login, image):
    response = admin_login.get(
        reverse("admin:images_image_changelist"), {"q": image.user.username}
    )

    assert response.status_code == 200
    assert image.title.encode() in response.content
