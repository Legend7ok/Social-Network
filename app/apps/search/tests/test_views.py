import pytest
from django.urls import reverse


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
def test_unknown_tab_falls_back_to_images(logged_client, images):
    response = logged_client.get(
        reverse("search:search"), {"q": "sunset", "tab": "moon"}
    )

    assert response.context["tab"] == "images"
    assert "images" in response.context


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
    assert "images/partials/image_cards.html" in rendered
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
