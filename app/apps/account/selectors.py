from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, IntegerField, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce

from apps.images.models import Image

from .models import Contact

User = get_user_model()

SIDEBAR_FOLLOWING_LIMIT = 8


def public_users():
    """People that may show up anywhere on the public side of the site."""
    return User.objects.filter(is_active=True, is_staff=False, is_superuser=False)


def sidebar_following(user):
    """The handful of people the right-hand sidebar lists, with the image count
    it shows under each name. Every page carrying that sidebar asks for the same
    thing, so the query lives in one place — and counting here rather than in
    the template turns eight queries per page into none."""
    return (
        public_users()
        .filter(profile__in=user.profile.following.all())
        .select_related("profile")
        .annotate(images_count=Count("images"))[:SIDEBAR_FOLLOWING_LIMIT]
    )


def is_followed_by(viewer):
    """Whether the viewer already follows the person a row is about."""
    return Exists(
        Contact.objects.filter(user_from=viewer.profile, user_to__user=OuterRef("pk"))
    )


def follows(viewer, person_id):
    """Whether the viewer already follows one particular person.

    The page used to answer this by pulling every follower of that person into
    memory and looking for itself among them.
    """
    return Contact.objects.filter(
        user_from=viewer.profile, user_to__user=person_id
    ).exists()


def _first_number(subquery):
    """A grouped subquery returns one row or none; none means zero."""
    return Coalesce(Subquery(subquery, output_field=IntegerField()), 0)


def followers_count(user_field="pk"):
    """How many people follow the person a row points at.

    A subquery rather than a join, so it can be annotated onto rows that
    already carry counts of their own without the two multiplying each other.
    `user_field` names the column holding that person — "pk" on a row that is
    the person, "user" on a row that merely belongs to them.
    """
    followers = Contact.objects.filter(user_to__user=OuterRef(user_field)).values(
        "user_to"
    )
    return _first_number(followers.annotate(n=Count("id")).values("n"))


def with_profile_counters(people, viewer):
    """The four numbers in the profile header, plus whether the viewer already
    follows this person.

    Separate subqueries rather than joined Count/Sum: joining images and
    contacts in one query multiplies their rows against each other, and every
    number would come out wrong.
    """
    images = Image.objects.filter(user=OuterRef("pk")).values("user")
    following = Contact.objects.filter(user_from__user=OuterRef("pk")).values(
        "user_from"
    )
    return people.annotate(
        images_count=_first_number(images.annotate(n=Count("id")).values("n")),
        total_likes=_first_number(images.annotate(n=Sum("total_likes")).values("n")),
        followers_count=followers_count(),
        following_count=_first_number(following.annotate(n=Count("id")).values("n")),
        followed_by_viewer=is_followed_by(viewer),
    )


def with_card_counters(people):
    """Counters the people card shows. Kept apart so counting stays cheap."""
    likes_per_user = (
        Image.objects.filter(user=OuterRef("pk"))
        .values("user")
        .annotate(total=Sum("total_likes"))
        .values("total")
    )
    return people.select_related("profile").annotate(
        images_count=Count("images", distinct=True),
        followers_count=Count("profile__followers", distinct=True),
        total_likes=Coalesce(Subquery(likes_per_user, output_field=IntegerField()), 0),
    )
