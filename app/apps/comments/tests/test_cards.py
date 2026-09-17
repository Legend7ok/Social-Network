import re

import pytest
from django.urls import reverse

from apps.images.models import Image

pytestmark = pytest.mark.django_db


def shows_comment_count(content, number):
    return re.search(rf'ti-message-circle[^"]*"></i>\s*{number}\b', content)


def signed_in_page(client, person, url):
    client.force_login(person)
    return client.get(url).content.decode()


def test_the_bookmarks_card_counts_comments(client, image, user):
    """Read from the column the signals keep, so a whole page of cards costs
    no query more than it did before."""
    owner, _ = user
    Image.objects.filter(pk=image.pk).update(total_comments=7)

    content = signed_in_page(client, owner, reverse("images:list"))

    assert shows_comment_count(content, 7)


def test_the_profile_grid_counts_comments(client, image, user):
    owner, _ = user
    Image.objects.filter(pk=image.pk).update(total_comments=7)

    content = signed_in_page(client, owner, reverse("my_profile"))

    assert shows_comment_count(content, 7)


def test_the_podium_and_the_rows_below_it_count_comments(client, user):
    """Four pictures: three for the podium, one left over for the list."""
    owner, _ = user
    for n in range(4):
        Image.objects.create(
            user=owner,
            title=f"Picture {n}",
            url=f"https://example.com/{n}.png",
            total_views=100 - n,
            total_comments=10 + n,
        )

    content = signed_in_page(client, owner, reverse("images:ranking"))

    assert all(shows_comment_count(content, 10 + n) for n in range(4))


def test_the_picture_page_takes_the_reader_down_to_the_conversation(client, image):
    content = client.get(
        reverse("images:detail", args=[image.id, image.slug])
    ).content.decode()

    assert 'href="#comments"' in content
    assert 'id="comments"' in content
