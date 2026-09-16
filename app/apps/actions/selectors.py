from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.prefetch import GenericPrefetch
from django.db.models import Exists, OuterRef

from apps.account.selectors import is_followed_by, public_users, with_card_counters
from apps.comments.models import Comment
from apps.images.models import Image

from .models import Action

User = get_user_model()


def feed(viewer):
    """Everyone's activity except the viewer's own.

    A target is fetched through a queryset of its own kind, already carrying
    the numbers and the toggle state its card shows, so a page of entries costs
    the same few queries whatever mix of cards it turns out to hold.
    """
    return (
        Action.objects.filter(user__in=public_users())
        .exclude(user=viewer)
        # A hidden person is hidden as a target too, or "alice is following
        # @admin" walks the service account back onto the page.
        .exclude(
            target_ct=ContentType.objects.get_for_model(User),
            target_id__in=User.objects.exclude(pk__in=public_users()).values("pk"),
        )
        # Words taken off the picture they were said under have no business
        # being read here instead. The signal drops the entry as well; this is
        # what answers for the rows a signal never sees - a bulk update, a data
        # migration - and it costs one subquery.
        .exclude(
            target_ct=ContentType.objects.get_for_model(Comment),
            target_id__in=Comment.objects.filter(removed_at__isnull=False).values("pk"),
        )
        .select_related("user", "user__profile")
        .prefetch_related(
            GenericPrefetch(
                "target", [_liked_images(viewer), _people(viewer), _comments()]
            )
        )
    )


def _liked_images(viewer):
    return Image.objects.annotate(
        liked_by_viewer=Exists(viewer.images_liked.filter(pk=OuterRef("pk")))
    )


def _comments():
    """A comment arrives with the picture it sits under: the card prints what
    was said and sends the reader to the page it was said on."""
    return Comment.objects.select_related("image")


def _people(viewer):
    return with_card_counters(User.objects.all()).annotate(
        followed_by_viewer=is_followed_by(viewer)
    )
