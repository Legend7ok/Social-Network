from django.conf import settings
from django.db import models

from apps.images.models import Image

COMMENT_MAX_LENGTH = 1000


class CommentQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(removed_at__isnull=True)


class Comment(models.Model):
    """Words left under a picture, or an answer to another comment.

    Removal is a mark rather than a delete: an answer whose parent vanished
    would hang under nothing. Hiding is asked for explicitly through
    `visible()`, so the admin still sees what was taken down.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="comments", on_delete=models.CASCADE
    )
    image = models.ForeignKey(Image, related_name="comments", on_delete=models.CASCADE)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="replies", on_delete=models.CASCADE
    )
    body = models.TextField(max_length=COMMENT_MAX_LENGTH)
    created = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    # Kept because a comment can be taken down by two different people - the
    # one who wrote it and the one whose picture it sits under - and "who" is
    # the first thing asked when someone misses their own words.
    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="removed_comments",
        on_delete=models.SET_NULL,
    )

    objects = CommentQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(
                fields=["image", "-created", "-id"],
                condition=models.Q(parent__isnull=True),
                name="comment_roots_by_image",
            ),
            models.Index(
                fields=["parent", "created", "id"], name="comment_replies_by_parent"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(body=""), name="comment_body_not_empty"
            ),
        ]

    def __str__(self):
        return f"Comment by {self.user} on {self.image}"
