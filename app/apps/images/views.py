from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .forms import ImageBookmarkForm, ImageEditForm, ImageUploadForm
from .models import Image
from .services import (
    apply_live_views,
    record_image_view,
    get_image_views,
    is_first_view,
)
from .tasks import download_image, generate_image_thumbnails
from apps.account.selectors import (
    followers_count,
    follows,
    public_users,
    sidebar_following,
)
from apps.actions.models import Action
from apps.actions.utils import create_action
from core.pagination import cursor_page

# The podium is rendered separately from the list below it.
RANKING_TOP = 3
RANKING_PER_PAGE = 10
RANKING_SORTS = {
    "views": "-total_views",
    "likes": "-total_likes",
}

# Roughly four minutes of asking, which outlives the download and its retries.
STATUS_POLL_SLOWDOWN = 15
STATUS_POLL_LIMIT = 60

# Faces shown under a picture before the rest become a number. A popular
# picture used to hand every one of its likers to the template.
LIKED_BY_LIMIT = 10

# Fills the two-column grid beside the picture exactly.
MORE_FROM_AUTHOR = 4


def bookmarklet_launcher(request):
    js = render(request, "bookmarklet_launcher.js", {"site_url": settings.SITE_URL})
    return HttpResponse(js, content_type="application/javascript")


@login_required
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def image_create(request):
    if request.method == "POST":
        form = ImageBookmarkForm(request.POST)
        if form.is_valid():
            new_image = form.save(commit=False)
            new_image.user = request.user
            new_image.save()
            transaction.on_commit(
                lambda: download_image.delay(new_image.id, new_image.url)
            )
            create_action(request.user, Action.Verb.BOOKMARKED_IMAGE, new_image)
            messages.success(request, "Image added successfully")
            return redirect(new_image.get_absolute_url())
    else:
        form = ImageBookmarkForm(data=request.GET)

    return render(request, "images/create.html", {"form": form})


def image_detail(request, id, slug):
    image = get_object_or_404(
        Image.objects.select_related("user", "user__profile").annotate(
            author_followers=followers_count("user")
        ),
        id=id,
    )
    # Stale links redirect instead of 404. Temporary: a cached permanent one
    # would loop if a title is ever renamed back.
    if slug != image.slug:
        return redirect(image.get_absolute_url())

    if image.image:
        if request.user.is_authenticated:
            viewer_key = f"user:{request.user.id}"
        else:
            if not request.session.session_key:
                request.session.create()
            viewer_key = f"session:{request.session.session_key}"
        if is_first_view(image.id, viewer_key):
            record_image_view(image.id)
        total_views = get_image_views(image.id)
    else:
        total_views = 0

    likers = public_users().filter(images_liked=image).select_related("profile")
    # Counted over the same filtered set the faces come from, so the "and N
    # more" cannot disagree with what is on screen.
    likes_count = likers.count()
    users_like = likers[:LIKED_BY_LIMIT]

    # Asked of the database rather than searched for in the list above: the
    # answer is one row either way, and the list is now only its first page.
    liked_by_viewer = (
        request.user.is_authenticated
        and image.users_like.filter(pk=request.user.pk).exists()
    )

    following_author = request.user.is_authenticated and follows(
        request.user, image.user_id
    )

    # The picture being looked at is not "more from this author".
    more_from_author = Image.objects.filter(user_id=image.user_id).exclude(pk=image.pk)[
        :MORE_FROM_AUTHOR
    ]

    following_users = (
        sidebar_following(request.user) if request.user.is_authenticated else []
    )

    return render(
        request,
        "images/detail.html",
        {
            "image": image,
            "total_views": total_views,
            "users_like": users_like,
            "hidden_likers": max(likes_count - LIKED_BY_LIMIT, 0),
            "liked_by_viewer": liked_by_viewer,
            "following_author": following_author,
            "more_from_author": more_from_author,
            "following_users": following_users,
        },
    )


@login_required
def image_list(request):
    mine = request.GET.get("mine")
    images = Image.objects.select_related("user", "user__profile")
    if mine:
        images = images.filter(user=request.user)

    page = cursor_page(
        images, settings.IMAGES_PER_PAGE, cursor=request.GET.get("after")
    )
    images_only = request.GET.get("images_only")
    if images_only and not page.rows:
        return HttpResponse("")

    apply_live_views(page.rows)

    context = {
        "images": page.rows,
        "next_cursor": page.next_cursor,
        "mine": mine,
    }

    if images_only:
        return render(request, "images/partials/image_cards.html", context)

    context["following_users"] = sidebar_following(request.user)
    return render(request, "images/list.html", context)


@login_required
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def image_upload(request):
    if request.method == "POST":
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            new_image = form.save(commit=False)
            new_image.user = request.user
            new_image.save()
            transaction.on_commit(lambda: generate_image_thumbnails.delay(new_image.id))
            create_action(request.user, Action.Verb.UPLOADED_IMAGE, new_image)
            messages.success(request, "Image uploaded successfully")
            return redirect(new_image.get_absolute_url())
    else:
        form = ImageUploadForm()
    return render(
        request,
        "images/upload.html",
        {"form": form, "max_upload_mb": settings.MAX_UPLOAD_SIZE // (1024 * 1024)},
    )


@login_required
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def image_edit(request, id):
    image = get_object_or_404(Image, id=id, user=request.user)

    if request.method == "POST":
        form = ImageEditForm(request.POST, instance=image)
        if form.is_valid():
            form.save()
            messages.success(request, "Image updated")
            return redirect(image.get_absolute_url())
    else:
        form = ImageEditForm(instance=image)

    return render(
        request,
        "images/edit.html",
        {"form": form, "image": image},
    )


@login_required
@require_POST
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def image_delete(request, id):
    # Filtering by author means someone else's image is a 404 rather than a
    # 403: there is nothing to say about images that are not yours.
    image = get_object_or_404(Image, id=id, user=request.user)
    # The page it was deleted from is one of the places to send it back to, and
    # the image's own page is not: it no longer exists a line below.
    image_url = image.get_absolute_url()
    image.delete()
    messages.success(request, "Image deleted")

    # Deletion is offered on several pages now, so it returns to the one it was
    # started from. Checked before use: an unchecked next is an open redirect.
    next_url = request.POST.get("next")
    if (
        next_url
        and next_url != image_url
        and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )
    ):
        return redirect(next_url)
    return redirect(f"{reverse('images:list')}?mine=1")


@login_required
@require_POST
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def image_retry_download(request, id):
    image = get_object_or_404(Image, id=id, user=request.user)

    if not image.image:
        # Clearing the reason is what puts the page back into waiting; the
        # column is written on its own so a stale copy cannot undo an edit.
        Image.objects.filter(id=image.id).update(download_error="")
        transaction.on_commit(lambda: download_image.delay(image.id, image.url))
        messages.success(request, "Fetching the image again")

    return redirect(image.get_absolute_url())


def image_status(request, id):
    image = get_object_or_404(Image, id=id)
    attempt = request.GET.get("attempt", "")
    attempt = int(attempt) if attempt.isdigit() else 0

    return render(
        request,
        "images/partials/image_status.html",
        {
            "image": image,
            "next_attempt": attempt + 1,
            # Slow down once the quick cases are past, and stop asking
            # altogether when nobody is going to answer: a worker that never
            # took the job leaves neither a file nor a reason behind.
            "poll_interval": "2s" if attempt < STATUS_POLL_SLOWDOWN else "5s",
            "polling_stopped": attempt >= STATUS_POLL_LIMIT,
        },
    )


@login_required
def image_ranking(request):
    sort = request.GET.get("sort", "views")
    if sort not in RANKING_SORTS:
        sort = "views"
    ranking_only = request.GET.get("ranking_only")

    # Ties are broken by id so an image cannot drift across page boundaries
    # while the reader pages through equal scores.
    ranked = Image.objects.select_related("user", "user__profile").order_by(
        RANKING_SORTS[sort], "-id"
    )

    # A podium with empty slots reads as broken — half of it would link
    # nowhere and the tiles would sit off-centre. Until three places are taken
    # the ranking is a plain numbered list built from the same rows.
    podium_size = RANKING_TOP if ranked.count() >= RANKING_TOP else 0

    paginator = Paginator(ranked[podium_size:], RANKING_PER_PAGE)
    try:
        page = paginator.page(request.GET.get("page"))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        if ranking_only:
            return HttpResponse("")
        page = paginator.page(paginator.num_pages)

    ranking_list = list(page.object_list)
    first_rank = podium_size + (page.number - 1) * RANKING_PER_PAGE + 1
    for offset, img in enumerate(ranking_list):
        img.rank = first_rank + offset

    context = {
        "sort": sort,
        "ranking_list": ranking_list,
        "has_next": page.has_next(),
        "next_page": page.number + 1,
    }

    if ranking_only:
        apply_live_views(ranking_list)
        return render(request, "images/partials/ranking_rows.html", context)

    top3 = list(ranked[:podium_size]) if podium_size else []
    for rank, img in enumerate(top3, start=1):
        img.rank = rank
    # Both halves of the page in one Redis round trip
    apply_live_views(ranking_list + top3)

    following_users = sidebar_following(request.user)

    context |= {"top3": top3, "following_users": following_users}
    return render(request, "images/ranking.html", context)
