from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.functions import Lower
from django.conf import settings


def users_with_email(email):
    """Matches on Lower("email") so the lookup hits the auth_user_email_ci_uniq
    index; iexact would compile to UPPER() and force a full scan instead."""
    # Resolved per call: models.py is imported while the app registry is still
    # loading, and asking for the user model at that point raises.
    return (
        get_user_model()
        .objects.annotate(email_lower=Lower("email"))
        .filter(email_lower=email)
    )


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_of_birth = models.DateField(blank=True, null=True)
    photo = models.ImageField(upload_to="users/%Y/%m/%d/", blank=True)
    following = models.ManyToManyField(
        "self",
        through="Contact",
        related_name="followers",
        symmetrical=False,
    )

    def __str__(self):
        return f"Profile of {self.user.username}"


class Contact(models.Model):
    user_from = models.ForeignKey(
        Profile, related_name="rel_from_set", on_delete=models.CASCADE
    )
    user_to = models.ForeignKey(
        Profile, related_name="rel_to_set", on_delete=models.CASCADE
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["-created"]),
        ]
        ordering = ["-created"]

    def __str__(self):
        return f"{self.user_from} follows {self.user_to}"
