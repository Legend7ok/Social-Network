from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.images.models import Image

from .forms import CommentForm
from .models import Comment
from .selectors import comments_page


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
        {"image": image, "comments": page.rows, "next_cursor": page.next_cursor},
    )


@login_required
@require_POST
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def comment_create(request, image_id):
    """Say something under a picture, or answer someone who already did."""
    image = get_object_or_404(Image, id=image_id)
    parent = _answered_comment(request, image)

    form = CommentForm(request.POST)
    form.instance.user = request.user
    form.instance.image = image
    form.instance.parent = parent
    if form.is_valid():
        form.save()
    else:
        messages.error(request, form.errors.get("body", ["Nothing was posted"])[0])

    return redirect(image.get_absolute_url())


@login_required
@require_POST
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def comment_remove(request, comment_id):
    """Take a comment off the page - your own words, or someone else's under
    your own picture. Anyone else's comment is a 404: there is nothing to say
    about words that are not yours to take down."""
    comment = get_object_or_404(
        Comment.objects.select_related("image").filter(
            Q(user=request.user) | Q(image__user=request.user)
        ),
        pk=comment_id,
    )
    # Pressing it twice - a second tab, a slow answer - must not move the hour
    # it was taken down, and must not name a second person as the one who did.
    if comment.removed_at is None:
        comment.removed_at = timezone.now()
        comment.removed_by = request.user
        comment.save(update_fields=["removed_at", "removed_by"])

    return redirect(comment.image.get_absolute_url())


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
