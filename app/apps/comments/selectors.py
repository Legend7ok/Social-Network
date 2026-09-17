from django.conf import settings
from django.db.models import Count, Exists, OuterRef, Q, Window
from django.db.models.functions import RowNumber

from core.pagination import cursor_page

from .models import Comment

# Answers shown under a comment before the reader asks for the rest.
PREVIEW_REPLIES = 2


def image_comments(image):
    """The conversation under a picture, newest first.

    A comment that was taken down stays in the list only while answers to it
    are still readable: dropping it would leave those answers hanging under
    nothing, so the template puts a tombstone in its place instead.
    """
    answered = Exists(Comment.objects.filter(parent=OuterRef("pk")).visible())
    return (
        Comment.objects.filter(image=image, parent__isnull=True)
        .filter(Q(removed_at__isnull=True) | answered)
        .select_related("user", "user__profile")
        .order_by("-created", "-id")
    )


def comments_page(image, cursor=None):
    """One page of the conversation, answers already hanging on it.

    The page a picture opens with and every page fetched after it come from
    here, so the two cannot drift apart.
    """
    page = cursor_page(image_comments(image), settings.COMMENTS_PER_PAGE, cursor=cursor)
    attach_replies(page.rows)
    return page


def thread_replies(root):
    """Every readable answer to one comment, oldest first - a thread reads as
    a conversation, top to bottom, while the comments above it read as news."""
    return (
        Comment.objects.filter(parent=root)
        .visible()
        .select_related("user", "user__profile")
        .order_by("created", "id")
    )


def attach_whole_thread(root):
    """The attributes `attach_replies` hangs on a comment, holding every
    readable answer instead of the first few.

    For redrawing a thread after something changed inside it: past the answers
    the page shows, the rest is sliced off by number, and a change among the
    first ones would shift an answer across that line and out of sight.
    """
    root.preview_replies = list(thread_replies(root))
    root.more_replies = 0


def attach_replies(roots):
    """Hang the first few answers on every comment of the page, with the
    number left unread behind them.

    One query for the whole page, whatever it holds: the database numbers the
    answers of each comment and hands back only the first of them, so a thread
    of five hundred costs the same as a thread of two. Callers pass a list,
    not a queryset - the attributes have to survive the template walking it.
    """
    by_id = {root.pk: root for root in roots}
    for root in roots:
        root.preview_replies = []
        root.more_replies = 0
    if not by_id:
        return

    rows = (
        Comment.objects.filter(parent_id__in=by_id)
        .visible()
        .select_related("user", "user__profile")
        .annotate(
            position=Window(
                RowNumber(), partition_by="parent", order_by=["created", "id"]
            ),
            thread_size=Window(Count("id"), partition_by="parent"),
        )
        .filter(position__lte=PREVIEW_REPLIES)
        .order_by("created", "id")
    )

    for reply in rows:
        root = by_id[reply.parent_id]
        root.preview_replies.append(reply)
        root.more_replies = max(reply.thread_size - PREVIEW_REPLIES, 0)
