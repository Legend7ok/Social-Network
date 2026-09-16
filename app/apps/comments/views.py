from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.actions.models import Action
from apps.actions.utils import create_action
from apps.images.models import Image

from .forms import CommentForm
from .models import Comment
from .selectors import (
    PREVIEW_REPLIES,
    attach_replies,
    attach_whole_thread,
    comments_page,
    thread_replies,
)


def comment_list(request, image_id):
    """The next page of the conversation under a picture.

    Public, like the picture page it belongs to: a guest reads what people
    said there, he only cannot answer.
    """
    image = get_object_or_404(Image, id=image_id)
    page = comments_page(image, request.GET.get("after"))
    # An empty answer tells htmx there is nothing more to hang on the page.
    if not page.rows:
        return HttpResponse("")

    return render(
        request,
        "comments/partials/comment_rows.html",
        {
            "image": image,
            "comments": page.rows,
            "next_cursor": page.next_cursor,
            "comment_form": CommentForm(),
        },
    )


def comment_thread(request, comment_id):
    """The rest of a thread: everything past the answers already on the page.

    Numbered pages rather than a cursor, unlike everywhere else on the site. A
    cursor is there to keep a list that grows from the top from shifting under
    the reader; a thread grows at the bottom, so page two stays page two.

    A comment taken down keeps its thread - that is what the tombstone in its
    place is for - so nothing here asks whether the root is still readable.
    """
    root = get_object_or_404(
        Comment.objects.select_related("image"), pk=comment_id, parent__isnull=True
    )
    paginator = Paginator(
        thread_replies(root)[PREVIEW_REPLIES:], settings.REPLIES_PER_PAGE
    )
    try:
        page = paginator.page(request.GET.get("page"))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        return HttpResponse("")

    return render(
        request,
        "comments/partials/reply_rows.html",
        {
            "image": root.image,
            "root": root,
            "replies": page.object_list,
            "has_next": page.has_next(),
            "next_page": page.number + 1,
        },
    )


@login_required
@require_POST
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def comment_create(request, image_id):
    """Say something under a picture, or answer someone who already did.

    One address for both kinds of form. A plain one goes back to the picture,
    the way any form does. htmx gets a fresh form in place of the one it sent,
    with the new comment - or, for an answer, its whole thread redrawn - and
    the new count carried alongside for the page to put where they belong.
    """
    image = get_object_or_404(Image, id=image_id)
    parent = _answered_comment(request, image)
    from_htmx = request.headers.get("HX-Request") == "true"

    form = CommentForm(request.POST)
    form.instance.user = request.user
    form.instance.image = image
    form.instance.parent = parent
    if not form.is_valid():
        if from_htmx:
            template = "form.html" if parent is None else "reply_form.html"
            return render(
                request,
                f"comments/partials/{template}",
                {"image": image, "root": parent, "form": form},
            )
        messages.error(request, form.errors.get("body", ["Nothing was posted"])[0])
        return redirect(image.get_absolute_url())

    comment = form.save()
    # Answers stay off the feed - they are the fabric of one conversation, and
    # a busy thread would push everyone else off the page. Commenting on your
    # own picture is not news either: an author answering twenty people would
    # otherwise hold the whole feed to himself.
    if parent is None and image.user_id != request.user.id:
        create_action(request.user, Action.Verb.COMMENTED_IMAGE, comment)

    if not from_htmx:
        return redirect(image.get_absolute_url())

    # The signal moved the counter in the database, not on this copy.
    image.refresh_from_db(fields=["total_comments"])
    fresh_form = CommentForm()

    if parent is not None:
        return render(
            request,
            "comments/partials/posted_reply.html",
            {
                "image": image,
                "root": parent,
                "replies": thread_replies(parent),
                "form": fresh_form,
                "posted": True,
            },
        )

    attach_replies([comment])
    return render(
        request,
        "comments/partials/posted.html",
        {
            "image": image,
            "comment": comment,
            "form": fresh_form,
            "comment_form": fresh_form,
        },
    )


@login_required
@require_POST
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def comment_remove(request, comment_id):
    """Take a comment off the page - your own words, or someone else's under
    your own picture. Anyone else's comment is a 404: there is nothing to say
    about words that are not yours to take down.

    htmx gets the comment the removal happened in, redrawn: the comment itself
    or the one an answer sat under. It comes back as a tombstone while answers
    remain under it, and as nothing once none do.
    """
    comment = get_object_or_404(
        Comment.objects.select_related("image", "parent").filter(
            Q(user=request.user) | Q(image__user=request.user)
        ),
        pk=comment_id,
    )
    image = comment.image
    # Pressing it twice - a second tab, a slow answer - must not move the hour
    # it was taken down, and must not name a second person as the one who did.
    if comment.removed_at is None:
        comment.removed_at = timezone.now()
        comment.removed_by = request.user
        comment.save(update_fields=["removed_at", "removed_by"])

    if request.headers.get("HX-Request") != "true":
        return redirect(image.get_absolute_url())

    if comment.parent_id is None:
        root = comment
        attach_replies([root])
    else:
        root = comment.parent
        attach_whole_thread(root)
    image.refresh_from_db(fields=["total_comments"])

    return render(
        request,
        "comments/partials/removed.html",
        {
            "image": image,
            "comment": root,
            "show_root": root.removed_at is None or bool(root.preview_replies),
            "comment_form": CommentForm(),
        },
    )


def _answered_comment(request, image):
    """The comment this one answers, or nothing if it answers no one.

    Everything that can be wrong with it is a 404 rather than an error on the
    form: a parent under another picture, an answer to an answer or a comment
    already taken down is never what the page itself sends.
    """
    parent_id = request.POST.get("parent", "")
    if not parent_id:
        return None
    if not parent_id.isdigit():
        raise Http404("No such comment")
    return get_object_or_404(
        Comment.objects.visible(), pk=parent_id, image=image, parent__isnull=True
    )
