import pytest
import requests
from unittest.mock import MagicMock, patch

from django.conf import settings

from apps.images.models import Image
from apps.images.tasks import download_image, generate_image_thumbnails
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
    mock_resp.iter_content = MagicMock(return_value=[MINIMAL_PNG])
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
    mock_resp.iter_content = MagicMock(return_value=[MINIMAL_PNG])
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
    mock_resp.iter_content = MagicMock(return_value=[MINIMAL_PNG])
    mock_resp.raise_for_status = MagicMock()

    with patch("apps.images.tasks.requests.get", return_value=mock_resp):
        with patch("apps.images.tasks.get_thumbnail") as mock_thumb:
            download_image(image.id, image.url)

    assert mock_thumb.call_count == 3


@pytest.mark.django_db
def test_generate_image_thumbnails_creates_content_set(image):
    with patch("apps.images.tasks.get_thumbnail") as mock_thumb:
        generate_image_thumbnails(image.id)

    thumbs = settings.THUMBNAILS
    calls = mock_thumb.call_args_list
    assert mock_thumb.call_count == 3
    # content_card / content_square are cropped; detail_main keeps the full image
    assert calls[0].args[1] == thumbs["content_card"]
    assert calls[0].kwargs == {"crop": "center"}
    assert calls[1].args[1] == thumbs["content_square"]
    assert calls[1].kwargs == {"crop": "center"}
    assert calls[2].args[1] == thumbs["detail_main"]
    assert calls[2].kwargs == {}


@pytest.mark.django_db
def test_generate_image_thumbnails_missing_image_skips():
    with patch("apps.images.tasks.get_thumbnail") as mock_thumb:
        generate_image_thumbnails(9999)
    mock_thumb.assert_not_called()


@pytest.mark.django_db
def test_generate_image_thumbnails_no_file_skips(user):
    user_obj, _ = user
    img = Image.objects.create(
        user=user_obj, title="No File", url="https://example.com/x.jpg"
    )
    with patch("apps.images.tasks.get_thumbnail") as mock_thumb:
        generate_image_thumbnails(img.id)
    mock_thumb.assert_not_called()


@pytest.mark.django_db
def test_download_image_silently_ignores_missing_image():
    download_image(9999, "https://example.com/test.jpg")


@pytest.mark.django_db
def test_download_image_discards_oversized_file(user):
    user_obj, _ = user
    image = Image.objects.create(
        user=user_obj,
        title="Huge Image",
        url="https://example.com/huge.jpg",
    )
    oversized = b"x" * (settings.MAX_UPLOAD_SIZE + 1)
    mock_resp = MagicMock()
    mock_resp.iter_content = MagicMock(return_value=[oversized])
    mock_resp.raise_for_status = MagicMock()

    with patch("apps.images.tasks.requests.get", return_value=mock_resp):
        with patch("apps.images.tasks.get_thumbnail") as mock_thumb:
            download_image(image.id, image.url)

    assert not Image.objects.filter(id=image.id).exists()
    mock_thumb.assert_not_called()


@pytest.mark.django_db
def test_download_image_raises_on_request_error(user):
    user_obj, _ = user
    image = Image.objects.create(
        user=user_obj,
        title="Test Image",
        url="https://example.com/test.jpg",
    )
    with patch(
        "apps.images.tasks.requests.get",
        side_effect=requests.RequestException("timeout"),
    ):
        with pytest.raises(requests.RequestException):
            download_image(image.id, image.url)
