import pytest
from django.urls import reverse

from apps.comments.models import Comment

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}


def detail_url(image):
    return reverse("images:detail", args=[image.id, image.slug])


def add_url(image):
    return reverse("comments:create", args=[image.id])


def test_a_guest_reads_the_comments_but_gets_no_form(client, image, user):
    author, _ = user
    Comment.objects.create(image=image, user=author, body="Lovely light")

    response = client.get(detail_url(image))

    assert b"Lovely light" in response.content
    assert b'id="comments-count">1<' in response.content
    assert b'name="body"' not in response.content


def test_a_member_gets_the_form(client, image, user):
    author, _ = user
    client.force_login(author)

    response = client.get(detail_url(image))

    assert b'name="body"' in response.content


def test_a_picture_without_comments_says_so(client, image):
    response = client.get(detail_url(image))

    assert b"No comments yet." in response.content


def test_a_comment_sent_by_htmx_comes_back_ready_to_be_placed(
    client, image, second_user
):
    """A fresh form for the place of the old one, and the comment and the
    count carried alongside - each addressed to where it goes on the page."""
    visitor, _ = second_user
    client.force_login(visitor)

    response = client.post(add_url(image), {"body": "Lovely light"}, **HTMX)

    content = response.content.decode()
    assert response.status_code == 200
    assert 'hx-swap-oob="afterbegin:#comments-list"' in content
    assert "Lovely light" in content
    assert '<span id="comments-count" hx-swap-oob="true">1</span>' in content
    assert "<textarea" in content and "Lovely light</textarea>" not in content


def test_a_refused_comment_sent_by_htmx_comes_back_as_the_form_with_its_error(
    client, image, second_user
):
    visitor, _ = second_user
    client.force_login(visitor)

    response = client.post(add_url(image), {"body": "   "}, **HTMX)

    content = response.content.decode()
    assert response.status_code == 200
    assert "Write something first" in content
    assert "hx-swap-oob" not in content
    assert Comment.objects.count() == 0


def test_the_plain_form_still_goes_back_to_the_picture(client, image, second_user):
    """Without JavaScript the same address answers the way it always did."""
    visitor, _ = second_user
    client.force_login(visitor)

    response = client.post(add_url(image), {"body": "Lovely light"})

    assert response.status_code == 302
    assert response.url == image.get_absolute_url()
