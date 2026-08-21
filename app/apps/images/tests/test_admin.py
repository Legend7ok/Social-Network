import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_image_changelist_opens(admin_client, image):
    response = admin_client.get(reverse("admin:images_image_changelist"))

    assert response.status_code == 200
    assert image.title.encode() in response.content


@pytest.mark.django_db
def test_image_change_form_opens(admin_client, image):
    response = admin_client.get(
        reverse("admin:images_image_change", args=[image.id]),
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_image_search_finds_by_author(admin_client, image):
    response = admin_client.get(
        reverse("admin:images_image_changelist"), {"q": image.user.username}
    )

    assert response.status_code == 200
    assert image.title.encode() in response.content
