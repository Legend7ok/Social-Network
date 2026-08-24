import pytest

from apps.account.models import Contact
from apps.account.selectors import with_card_counters
from apps.images.models import Image
from apps.search.selectors import search_images, search_users


@pytest.mark.django_db
def test_title_match_ranks_above_description_match(images):
    results = search_images("sunset")

    assert [image.title for image in results] == [
        "Sunset over the sea",
        "Calm morning",
    ]


@pytest.mark.django_db
def test_search_matches_other_word_forms(images):
    assert [image.title for image in search_images("spheres")] == [
        "Abstract glass sphere"
    ]


@pytest.mark.django_db
def test_search_ignores_broken_syntax(images):
    assert search_images("sunset ((").count() == 2


@pytest.mark.django_db
def test_search_without_matches_is_empty(images):
    assert search_images("helicopter").count() == 0


@pytest.mark.django_db
def test_people_search_survives_a_typo(people):
    assert [person.username for person in search_users("tkachenk")] == [
        people["dmytro"].username
    ]


@pytest.mark.django_db
def test_people_search_matches_last_name(people):
    assert [person.username for person in search_users("Petrov")] == [
        people["maria"].username
    ]


@pytest.mark.django_db
def test_people_search_hides_staff_accounts(people):
    assert search_users("adminuser").count() == 0


@pytest.mark.django_db
def test_people_search_annotates_card_counters(people):
    dmytro, maria = people["dmytro"], people["maria"]
    Image.objects.create(
        user=dmytro,
        title="Sunset over the sea",
        url="https://example.com/photo.jpg",
        total_likes=5,
    )
    Contact.objects.create(user_from=maria.profile, user_to=dmytro.profile)

    found = with_card_counters(search_users("tkachenkodm")).get()

    assert found.images_count == 1
    assert found.followers_count == 1
    assert found.total_likes == 5
