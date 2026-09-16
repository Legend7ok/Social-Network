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


def test_a_member_can_answer_a_comment_and_its_replies(
    client, image, user, second_user
):
    author, _ = user
    answerer, _ = second_user
    root = Comment.objects.create(image=image, user=author, body="Root")
    Comment.objects.create(image=image, user=answerer, body="Thanks", parent=root)
    client.force_login(author)

    content = client.get(detail_url(image)).content.decode()

    assert "open('alice')" in content
    assert "open('bob')" in content
    assert f'name="parent" value="{root.id}"' in content


def test_a_guest_gets_no_reply_buttons(client, image, user, second_user):
    author, _ = user
    answerer, _ = second_user
    root = Comment.objects.create(image=image, user=author, body="Root")
    Comment.objects.create(image=image, user=answerer, body="Thanks", parent=root)

    content = client.get(detail_url(image)).content.decode()

    assert "Thanks" in content
    assert "open(" not in content


def test_a_tombstone_takes_no_answers(client, image, user, second_user):
    """The thread under a deleted comment stays readable, but the server would
    refuse an answer to it - so no button offers one."""
    author, _ = user
    answerer, _ = second_user
    root = Comment.objects.create(image=image, user=author, body="Root")
    Comment.objects.create(image=image, user=answerer, body="Thanks", parent=root)
    client.force_login(author)
    client.post(reverse("comments:remove", args=[root.id]))

    content = client.get(detail_url(image)).content.decode()

    assert "Thanks" in content
    assert "open(" not in content
    assert 'name="parent"' not in content


def test_an_answer_sent_by_htmx_redraws_its_whole_thread(
    client, image, user, second_user
):
    """Past the answers the page already shows, the thread may still be
    unloaded. The answer brings the thread complete, so the button that would
    have loaded the rest cannot bring the new answer a second time."""
    author, _ = user
    answerer, _ = second_user
    root = Comment.objects.create(image=image, user=author, body="Root")
    for n in range(4):
        Comment.objects.create(
            image=image, user=author, body=f"Earlier {n}", parent=root
        )
    client.force_login(answerer)

    response = client.post(
        add_url(image), {"body": "@alice agreed", "parent": root.id}, **HTMX
    )

    content = response.content.decode()
    assert f'id="thread-{root.id}"' in content
    assert 'hx-swap-oob="true"' in content
    assert content.index("Earlier 0") < content.index("Earlier 3")
    assert content.index("Earlier 3") < content.index("@alice agreed")
    assert "more replies" not in content
    assert 'x-init="close()"' in content
    assert '<span id="comments-count" hx-swap-oob="true">6</span>' in content


def test_a_refused_answer_comes_back_as_the_answer_box(
    client, image, user, second_user
):
    author, _ = user
    answerer, _ = second_user
    root = Comment.objects.create(image=image, user=author, body="Root")
    client.force_login(answerer)

    response = client.post(add_url(image), {"body": " ", "parent": root.id}, **HTMX)

    content = response.content.decode()
    assert "Write something first" in content
    assert f'name="parent" value="{root.id}"' in content
    assert 'x-init="close()"' not in content


def remove_url(comment):
    return reverse("comments:remove", args=[comment.id])


def delete_buttons(content):
    return content.count("confirm-comment-removal', {")


def test_delete_is_offered_to_the_writer_and_to_the_owner_of_the_picture(
    client, image, user, second_user, make_user
):
    owner, _ = user
    visitor, _ = second_user
    bystander, _ = make_user("carol", "carol@example.com", "testpass321")
    Comment.objects.create(image=image, user=visitor, body="Lovely light")

    def page_seen_by(person):
        client.logout()
        if person:
            client.force_login(person)
        return client.get(detail_url(image)).content.decode()

    owner_page = page_seen_by(owner)
    visitor_page = page_seen_by(visitor)
    bystander_page = page_seen_by(bystander)
    guest_page = page_seen_by(None)

    assert delete_buttons(owner_page) == 1
    assert delete_buttons(visitor_page) == 1
    assert delete_buttons(bystander_page) == 0
    assert delete_buttons(guest_page) == 0


def test_a_removed_comment_without_answers_comes_back_as_nothing(
    client, image, second_user
):
    """The empty answer is what takes it off the page, and the count follows."""
    visitor, _ = second_user
    comment = Comment.objects.create(image=image, user=visitor, body="Lovely light")
    client.force_login(visitor)

    content = client.post(remove_url(comment), **HTMX).content.decode()

    assert "<article" not in content
    assert '<span id="comments-count" hx-swap-oob="true">0</span>' in content


def test_a_removed_comment_with_answers_comes_back_as_a_tombstone(
    client, image, user, second_user
):
    owner, _ = user
    visitor, _ = second_user
    root = Comment.objects.create(image=image, user=visitor, body="Taken down")
    Comment.objects.create(image=image, user=owner, body="Still here", parent=root)
    client.force_login(visitor)

    content = client.post(remove_url(root), **HTMX).content.decode()

    assert f'id="comment-{root.id}"' in content
    assert "Comment deleted" in content
    assert "Taken down" not in content
    assert "Still here" in content


def test_a_removed_answer_redraws_its_comment_with_the_whole_thread(
    client, image, user, second_user
):
    """Answers past the first ones are sliced off by number. Take one of the
    first away and the next would slip past that line unseen - unless the
    thread comes back whole."""
    owner, _ = user
    visitor, _ = second_user
    root = Comment.objects.create(image=image, user=owner, body="Root")
    answers = [
        Comment.objects.create(
            image=image, user=visitor, body=f"Answer {n}", parent=root
        )
        for n in range(5)
    ]
    client.force_login(visitor)

    content = client.post(remove_url(answers[0]), **HTMX).content.decode()

    assert f'id="comment-{root.id}"' in content
    assert "Answer 0" not in content
    assert all(f"Answer {n}" in content for n in range(1, 5))
    assert "more replies" not in content


def test_the_last_answer_under_a_tombstone_takes_the_tombstone_along(
    client, image, user, second_user
):
    owner, _ = user
    visitor, _ = second_user
    root = Comment.objects.create(image=image, user=visitor, body="Taken down")
    answer = Comment.objects.create(image=image, user=owner, body="Last", parent=root)
    client.force_login(visitor)
    client.post(remove_url(root), **HTMX)
    client.force_login(owner)

    content = client.post(remove_url(answer), **HTMX).content.decode()

    assert "<article" not in content


def test_the_plain_form_still_goes_back_to_the_picture(client, image, second_user):
    """Without JavaScript the same address answers the way it always did."""
    visitor, _ = second_user
    client.force_login(visitor)

    response = client.post(add_url(image), {"body": "Lovely light"})

    assert response.status_code == 302
    assert response.url == image.get_absolute_url()
