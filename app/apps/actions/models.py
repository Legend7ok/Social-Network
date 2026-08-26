from django.conf import settings
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class Action(models.Model):
    class Verb(models.TextChoices):
        """What the feed can say about someone. The stored value is the phrase
        itself, printed straight after the name: "alice likes <image>"."""

        CREATED_ACCOUNT = "has created an account"
        UPLOADED_IMAGE = "uploaded image"
        BOOKMARKED_IMAGE = "bookmarked image"
        LIKED_IMAGE = "likes"
        FOLLOWED_USER = "is following"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="actions", on_delete=models.CASCADE
    )
    verb = models.CharField(max_length=255, choices=Verb)
    created = models.DateTimeField(auto_now_add=True)
    target_ct = models.ForeignKey(
        ContentType,
        blank=True,
        null=True,
        related_name="target_obj",
        on_delete=models.CASCADE,
    )
    target_id = models.PositiveIntegerField(blank=True, null=True)

    target = GenericForeignKey("target_ct", "target_id")

    class Meta:
        indexes = [
            models.Index(fields=["-created", "-id"]),
            models.Index(fields=["target_ct", "target_id"]),
        ]
        ordering = ["-created", "-id"]
