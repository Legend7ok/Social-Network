import pytest
from django.urls import reverse
from django.utils import timezone

from apps.comments.models import Comment


@pytest.mark.django_db
def test_comment_changelist_opens(admin_client, image, user):
    author, _ = user
    Comment.objects.create(image=image, user=author, body="Lovely light")

    response = admin_client.get(reverse("admin:comments_comment_changelist"))

    assert response.status_code == 200
    assert b"Lovely light" in response.content


@pytest.mark.django_db
def test_comment_change_form_opens(admin_client, image, user):
    author, _ = user
    comment = Comment.objects.create(image=image, user=author, body="Lovely light")

    response = admin_client.get(
        reverse("admin:comments_comment_change", args=[comment.id])
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_taken_down_comment_is_still_listed(admin_client, image, user):
    """The site hides it, the admin must not: this is the only place left to
    read what was taken down and who took it down."""
    author, _ = user
    Comment.objects.create(
        image=image, user=author, body="Taken down", removed_at=timezone.now()
    )

    response = admin_client.get(reverse("admin:comments_comment_changelist"))

    assert b"Taken down" in response.content
