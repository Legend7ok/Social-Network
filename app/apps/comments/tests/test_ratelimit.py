import pytest
from django.urls import reverse

from apps.comments.models import Comment


@pytest.mark.django_db
def test_comment_create_rate_limit_returns_429(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    url = reverse("comments:create", args=[image.id])

    for _ in range(30):
        response = client.post(url, {"body": "Lovely light"})
        assert response.status_code == 302

    response = client.post(url, {"body": "One too many"})
    assert response.status_code == 429
    assert Comment.objects.count() == 30
