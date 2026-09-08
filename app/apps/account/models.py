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


def users_with_username(username):
    """Same idea for auth_user_username_ci_uniq: the stored casing is kept, but
    two people cannot hold the same name in different cases."""
    return (
        get_user_model()
        .objects.annotate(username_lower=Lower("username"))
        .filter(username_lower=username.lower())
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
        constraints = [
            # One row per pair. get_or_create reads before it writes, so two
            # requests racing each other (a double click, a second tab) both
            # saw nothing and both inserted; the follower count then showed
            # two, and the same person appeared twice in the list.
            models.UniqueConstraint(
                fields=["user_from", "user_to"], name="account_contact_from_to_uniq"
            ),
        ]
        ordering = ["-created"]

    def __str__(self):
        return f"{self.user_from} follows {self.user_to}"
