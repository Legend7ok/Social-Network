import pytest
from django.urls import reverse

from apps.images.models import Image


@pytest.mark.django_db
def test_search_requires_login(client):
    response = client.get(reverse("search:search"))

    assert response.status_code == 302


@pytest.mark.django_db
def test_empty_query_skips_the_search(logged_client):
    response = logged_client.get(reverse("search:search"))

    assert response.status_code == 200
    assert "images_count" not in response.context


@pytest.mark.django_db
def test_too_short_query_is_reported(logged_client):
    response = logged_client.get(reverse("search:search"), {"q": "a"})

    assert response.context["query_too_short"] is True
    assert "images_count" not in response.context


@pytest.mark.django_db
def test_both_tabs_are_counted(logged_client, images, people):
    response = logged_client.get(reverse("search:search"), {"q": "sunset"})

    assert response.context["images_count"] == 2
    assert response.context["people_count"] == 0
    assert [image.title for image in response.context["images"]] == [
        "Sunset over the sea",
        "Calm morning",
    ]


@pytest.mark.django_db
def test_nul_byte_in_query_is_dropped(logged_client, images):
    response = logged_client.get(reverse("search:search"), {"q": "sun\x00set"})

    assert response.status_code == 200
    assert response.context["images_count"] == 2


@pytest.mark.django_db
def test_overlong_query_is_cut(logged_client, images, settings):
    response = logged_client.get(reverse("search:search"), {"q": "sunset" + "o" * 5000})

    assert response.status_code == 200
    assert len(response.context["q"]) == settings.SEARCH_MAX_QUERY_LENGTH


@pytest.mark.django_db
def test_unknown_tab_is_ignored(logged_client, images):
    response = logged_client.get(
        reverse("search:search"), {"q": "sunset", "tab": "moon"}
    )

    assert response.context["tab"] == "images"
    assert "images" in response.context


@pytest.fixture
def more_people_than_images(user, people, make_person):
    user_obj, _ = user
    Image.objects.create(
        user=user_obj, title="Petrova at work", url="https://example.com/photo.jpg"
    )
    make_person("petrovaanna", "Anna", "Petrova")


@pytest.mark.django_db
def test_tab_opens_where_most_results_are(logged_client, more_people_than_images):
    response = logged_client.get(reverse("search:search"), {"q": "petrova"})

    assert response.context["images_count"] == 1
    assert response.context["people_count"] == 2
    assert response.context["tab"] == "people"


@pytest.mark.django_db
def test_picked_tab_beats_the_bigger_side(logged_client, more_people_than_images):
    response = logged_client.get(
        reverse("search:search"), {"q": "petrova", "tab": "images"}
    )

    assert response.context["tab"] == "images"


@pytest.mark.django_db
def test_people_tab_lists_people(logged_client, people):
    response = logged_client.get(
        reverse("search:search"), {"q": "tkachenk", "tab": "people"}
    )

    assert [person.username for person in response.context["users"]] == [
        people["dmytro"].username
    ]


@pytest.mark.django_db
def test_scroll_request_returns_cards_only(logged_client, images):
    response = logged_client.get(
        reverse("search:search"), {"q": "sunset", "images_only": "1"}
    )

    rendered = [template.name for template in response.templates]
    assert "search/partials/image_results.html" in rendered
    assert "search/results.html" not in rendered


@pytest.mark.django_db
def test_scroll_past_the_last_page_returns_nothing(logged_client, images):
    response = logged_client.get(
        reverse("search:search"), {"q": "sunset", "images_only": "1", "page": "99"}
    )

    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.django_db
def test_search_is_rate_limited(logged_client, settings):
    limit = int(settings.SEARCH_RATE.split("/")[0])

    for _ in range(limit):
        assert logged_client.get(reverse("search:search")).status_code == 200

    assert logged_client.get(reverse("search:search")).status_code == 429
