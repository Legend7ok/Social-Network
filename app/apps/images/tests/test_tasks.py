import pytest
from unittest.mock import MagicMock, patch

from apps.images.models import Image
from apps.images.tasks import download_image
from conftest import MINIMAL_PNG


@pytest.mark.django_db
def test_download_image_saves_file(user):
    user_obj, _ = user
    image = Image.objects.create(
        user=user_obj,
        title="Test Image",
        url="https://example.com/test.jpg",
    )
    mock_resp = MagicMock()
    mock_resp.content = MINIMAL_PNG
    mock_resp.raise_for_status = MagicMock()

    with patch("apps.images.tasks.requests.get", return_value=mock_resp):
        with patch("apps.images.tasks.get_thumbnail"):
            download_image(image.id, image.url)

    image.refresh_from_db()
    assert image.image
    assert image.image.name.endswith(".jpg")


@pytest.mark.django_db
def test_download_image_filename_uses_slugified_title(user):
    user_obj, _ = user
    image = Image.objects.create(
        user=user_obj,
        title="My Cool Image",
        url="https://example.com/photo.png",
    )
    mock_resp = MagicMock()
    mock_resp.content = MINIMAL_PNG
    mock_resp.raise_for_status = MagicMock()

    with patch("apps.images.tasks.requests.get", return_value=mock_resp):
        with patch("apps.images.tasks.get_thumbnail"):
            download_image(image.id, image.url)

    image.refresh_from_db()
    assert "my-cool-image" in image.image.name


@pytest.mark.django_db
def test_download_image_pregenerates_thumbnails(user):
    user_obj, _ = user
    image = Image.objects.create(
        user=user_obj,
        title="Test Image",
        url="https://example.com/test.jpg",
    )
    mock_resp = MagicMock()
    mock_resp.content = MINIMAL_PNG
    mock_resp.raise_for_status = MagicMock()

    with patch("apps.images.tasks.requests.get", return_value=mock_resp):
        with patch("apps.images.tasks.get_thumbnail") as mock_thumb:
            download_image(image.id, image.url)

    assert mock_thumb.call_count == 2


@pytest.mark.django_db
def test_download_image_silently_ignores_missing_image():
    download_image(9999, "https://example.com/test.jpg")


@pytest.mark.django_db
def test_download_image_silently_ignores_request_error(user):
    user_obj, _ = user
    image = Image.objects.create(
        user=user_obj,
        title="Test Image",
        url="https://example.com/test.jpg",
    )
    with patch("apps.images.tasks.requests.get", side_effect=Exception("timeout")):
        download_image(image.id, image.url)

    image.refresh_from_db()
    assert not image.image
