import pytest
import requests
from unittest.mock import MagicMock, patch

from django.conf import settings

from apps.actions.models import Action
from apps.actions.utils import create_action
from apps.images.models import Image
from apps.images.services import (
    DIRTY_IMAGES_KEY,
    clear_view_deltas,
    record_image_view,
)
from apps.images.tasks import (
    delete_image_artifacts,
    download_image,
    flush_image_views,
    generate_image_thumbnails,
)
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


# ─── flush_image_views ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_flush_image_views_adds_buffered_views_to_stored_total(image):
    Image.objects.filter(id=image.id).update(total_views=100)
    record_image_view(image.id)
    record_image_view(image.id)

    assert flush_image_views() == 1

    image.refresh_from_db()
    assert image.total_views == 102


@pytest.mark.django_db
def test_flush_image_views_drains_redis_and_dirty_set(fake_redis, image):
    record_image_view(image.id)

    flush_image_views()

    assert int(fake_redis.get(f"image:{image.id}:views")) == 0
    assert fake_redis.smembers(DIRTY_IMAGES_KEY) == set()


@pytest.mark.django_db
def test_flush_image_views_is_not_double_counted_on_repeat(image):
    record_image_view(image.id)

    flush_image_views()
    flush_image_views()

    image.refresh_from_db()
    assert image.total_views == 1


@pytest.mark.django_db
def test_flush_image_views_keeps_views_arriving_during_the_flush(fake_redis, image):
    record_image_view(image.id)
    # A view lands after the task read the counter but before it drains it.
    record_image_view(image.id)
    clear_view_deltas({image.id: 1})

    assert int(fake_redis.get(f"image:{image.id}:views")) == 1
    assert fake_redis.smembers(DIRTY_IMAGES_KEY) == {str(image.id).encode()}


@pytest.mark.django_db
def test_flush_image_views_forgets_deleted_images(fake_redis):
    record_image_view(9999)

    assert flush_image_views() == 0
    assert fake_redis.smembers(DIRTY_IMAGES_KEY) == set()


@pytest.mark.django_db
def test_flush_image_views_without_dirty_images_does_nothing():
    assert flush_image_views() == 0


# ─── delete_image_artifacts ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_delete_image_artifacts_clears_view_counters(fake_redis, image):
    record_image_view(image.id)

    delete_image_artifacts(image.id, "")

    assert fake_redis.get(f"image:{image.id}:views") is None
    assert fake_redis.smembers(DIRTY_IMAGES_KEY) == set()


@pytest.mark.django_db
def test_delete_image_artifacts_removes_actions_pointing_at_the_image(user, image):
    user_obj, _ = user
    create_action(user_obj, "uploaded image", image)

    delete_image_artifacts(image.id, "")

    assert not Action.objects.filter(verb="uploaded image").exists()


@pytest.mark.django_db
def test_delete_image_artifacts_keeps_actions_of_other_images(user, image):
    user_obj, _ = user
    other = Image.objects.create(
        user=user_obj, title="Other", url="https://example.com/other.png"
    )
    create_action(user_obj, "uploaded image", other)

    delete_image_artifacts(image.id, "")

    assert Action.objects.filter(target_id=other.id).exists()


@pytest.mark.django_db
def test_delete_image_artifacts_removes_file_and_thumbnails(image):
    file_name = image.image.name

    with patch("apps.images.tasks.delete_thumbnails") as mock_delete:
        delete_image_artifacts(image.id, file_name)

    mock_delete.assert_called_once_with(file_name)


@pytest.mark.django_db
def test_delete_image_artifacts_skips_storage_when_there_is_no_file(image):
    with patch("apps.images.tasks.delete_thumbnails") as mock_delete:
        delete_image_artifacts(image.id, "")

    mock_delete.assert_not_called()


@pytest.mark.django_db
def test_delete_image_artifacts_can_be_repeated(fake_redis, user, image):
    user_obj, _ = user
    create_action(user_obj, "uploaded image", image)
    record_image_view(image.id)

    with patch("apps.images.tasks.delete_thumbnails"):
        delete_image_artifacts(image.id, image.image.name)
        delete_image_artifacts(image.id, image.image.name)

    assert not Action.objects.filter(target_id=image.id).exists()
    assert fake_redis.get(f"image:{image.id}:views") is None


@pytest.mark.django_db
def test_flush_image_views_handles_several_images(user, image):
    user_obj, _ = user
    other = Image.objects.create(
        user=user_obj, title="Other", url="https://example.com/other.png"
    )
    record_image_view(image.id)
    record_image_view(other.id)
    record_image_view(other.id)

    assert flush_image_views() == 2

    image.refresh_from_db()
    other.refresh_from_db()
    assert image.total_views == 1
    assert other.total_views == 2
