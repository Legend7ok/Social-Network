from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.images.models import Image

from .forms import CommentForm
from .models import Comment


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
