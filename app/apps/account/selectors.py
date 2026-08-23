from django.contrib.auth import get_user_model
from django.db.models import Count, IntegerField, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce

from apps.images.models import Image

User = get_user_model()


def public_users():
    """People that may show up anywhere on the public side of the site."""
    return User.objects.filter(is_active=True, is_staff=False, is_superuser=False)


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
