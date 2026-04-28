import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.images.models import Image
from apps.images.services import get_image_ranking, record_image_view

MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def make_user(db):
    def _make(username, email, password):
        from django.contrib.auth import get_user_model

        from apps.account.models import Profile

        User = get_user_model()
        user_obj = User.objects.create_user(
            username=username, email=email, password=password
        )
        Profile.objects.create(user=user_obj)
        return user_obj, password

    return _make


@pytest.fixture
def user(make_user):
    return make_user("alice", "alice@example.com", "testpass123")


@pytest.fixture
def image(db, user):
    user_obj, _ = user
    img_file = SimpleUploadedFile("test.png", MINIMAL_PNG, content_type="image/png")
    return Image.objects.create(
        user=user_obj,
        title="Test Image",
        url="https://example.com/test.png",
        image=img_file,
    )


# ─── record_image_view ───────────────────────────────────────────────────────


def test_record_image_view_returns_int():
    result = record_image_view(1)
    assert isinstance(result, int)


def test_record_image_view_starts_at_one():
    assert record_image_view(42) == 1


def test_record_image_view_increments_on_each_call():
    record_image_view(1)
    assert record_image_view(1) == 2


def test_record_image_view_different_images_are_independent():
    record_image_view(1)
    record_image_view(1)
    assert record_image_view(2) == 1


def test_record_image_view_updates_ranking_sorted_set(fake_redis):
    record_image_view(10)
    assert fake_redis.zscore("image_ranking", 10) == 1.0


def test_record_image_view_increments_ranking_score(fake_redis):
    record_image_view(10)
    record_image_view(10)
    record_image_view(10)
    assert fake_redis.zscore("image_ranking", 10) == 3.0


# ─── get_image_ranking ───────────────────────────────────────────────────────


def test_get_image_ranking_empty_returns_empty_list():
    assert get_image_ranking() == []


def test_get_image_ranking_returns_python_ints():
    record_image_view(5)
    assert all(isinstance(i, int) for i in get_image_ranking())


def test_get_image_ranking_descending_order():
    for _ in range(3):
        record_image_view(1)
    for _ in range(5):
        record_image_view(2)
    record_image_view(3)
    assert get_image_ranking() == [2, 1, 3]


def test_get_image_ranking_respects_count_param():
    for image_id in range(1, 6):
        for _ in range(image_id):
            record_image_view(image_id)
    assert len(get_image_ranking(count=3)) == 3


def test_get_image_ranking_returns_all_when_fewer_than_count():
    record_image_view(1)
    record_image_view(2)
    assert len(get_image_ranking(count=10)) == 2


# ─── image_ranking view ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_image_ranking_redirects_anonymous_user(client):
    response = client.get(reverse("images:ranking"))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_image_ranking_returns_200_with_section_context(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:ranking"))
    assert response.status_code == 200
    assert response.context["section"] == "images"


@pytest.mark.django_db
def test_image_ranking_shows_most_viewed_first(client, user, image):
    user_obj, password = user
    img_file = SimpleUploadedFile("img2.png", MINIMAL_PNG, content_type="image/png")
    image2 = Image.objects.create(
        user=user_obj,
        title="Second Image",
        url="https://example.com/img2.png",
        image=img_file,
    )
    for _ in range(5):
        record_image_view(image2.id)
    record_image_view(image.id)

    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:ranking"))
    most_viewed = response.context["most_viewed"]
    assert most_viewed[0] == image2
    assert most_viewed[1] == image


@pytest.mark.django_db
def test_image_ranking_excludes_stale_redis_entries(client, user, image):
    user_obj, password = user
    record_image_view(9999)  # ID не существует в БД
    record_image_view(image.id)

    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:ranking"))
    ids = [img.id for img in response.context["most_viewed"]]
    assert 9999 not in ids
    assert image.id in ids
