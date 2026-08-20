from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django_ratelimit.decorators import ratelimit

from .forms import ImageBookmarkForm, ImageUploadForm
from .models import Image
from .services import (
    record_image_view,
    get_image_views,
    get_images_views,
    is_first_view,
)
from .tasks import download_image, generate_image_thumbnails
from apps.actions.utils import create_action

User = get_user_model()

# The podium is rendered separately from the list below it.
RANKING_TOP = 3
RANKING_PER_PAGE = 10
RANKING_SORTS = {
    "views": "-total_views",
    "likes": "-total_likes",
}


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
            download_image.delay(new_image.id, new_image.url)
            create_action(request.user, "bookmarked image", new_image)
            messages.success(request, "Image added successfully")
            return redirect(new_image.get_absolute_url())
    else:
        form = ImageBookmarkForm(data=request.GET)

    return render(request, "images/create.html", {"section": "images", "form": form})


def image_detail(request, id, slug):
    image = get_object_or_404(
        Image.objects.select_related("user", "user__profile"), id=id, slug=slug
    )
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

    users_like = image.users_like.select_related("profile").all()

    following_users = (
        User.objects.filter(
            profile__in=request.user.profile.following.all()
        ).select_related("profile")[:8]
        if request.user.is_authenticated
        else []
    )

    return render(
        request,
        "images/detail.html",
        {
            "section": "images",
            "image": image,
            "total_views": total_views,
            "users_like": users_like,
            "following_users": following_users,
        },
    )


@login_required
def image_list(request):
    mine = request.GET.get("mine")
    if mine:
        images = Image.objects.filter(user=request.user).select_related(
            "user", "user__profile"
        )
    else:
        images = Image.objects.all().select_related("user", "user__profile")
    paginator = Paginator(images, 6)
    page = request.GET.get("page")
    images_only = request.GET.get("images_only")
    try:
        images = paginator.page(page)
    except PageNotAnInteger:
        images = paginator.page(1)
    except EmptyPage:
        if images_only:
            return HttpResponse("")
        images = paginator.page(paginator.num_pages)

    # Force evaluation so total_views attrs survive template iteration
    images.object_list = list(images.object_list)
    views_map = get_images_views([img.id for img in images.object_list])
    for img in images.object_list:
        img.total_views = views_map.get(img.id, 0)

    following_users = User.objects.filter(
        profile__in=request.user.profile.following.all()
    ).select_related("profile")[:8]

    context = {
        "section": "images",
        "images": images,
        "following_users": following_users,
        "mine": mine,
    }

    if images_only:
        return render(request, "images/partials/image_cards.html", context)

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
            create_action(request.user, "uploaded image", new_image)
            messages.success(request, "Image uploaded successfully")
            return redirect(new_image.get_absolute_url())
    else:
        form = ImageUploadForm()
    return render(request, "images/upload.html", {"section": "images", "form": form})


def image_status(request, id):
    image = get_object_or_404(Image, id=id)
    return render(request, "images/partials/image_status.html", {"image": image})


def _show_live_views(images):
    """Overlay the counts still buffered in Redis on top of the stored ones."""
    views_map = get_images_views([img.id for img in images])
    for img in images:
        img.total_views = views_map.get(img.id, img.total_views)


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

    paginator = Paginator(ranked[RANKING_TOP:], RANKING_PER_PAGE)
    try:
        page = paginator.page(request.GET.get("page"))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        if ranking_only:
            return HttpResponse("")
        page = paginator.page(paginator.num_pages)

    ranking_list = list(page.object_list)
    first_rank = RANKING_TOP + (page.number - 1) * RANKING_PER_PAGE + 1
    for offset, img in enumerate(ranking_list):
        img.rank = first_rank + offset
    _show_live_views(ranking_list)

    context = {
        "section": "images",
        "sort": sort,
        "ranking_list": ranking_list,
        "has_next": page.has_next(),
        "next_page": page.number + 1,
    }

    if ranking_only:
        return render(request, "images/partials/ranking_rows.html", context)

    top3 = list(ranked[:RANKING_TOP])
    for rank, img in enumerate(top3, start=1):
        img.rank = rank
    _show_live_views(top3)

    following_users = User.objects.filter(
        profile__in=request.user.profile.following.all()
    ).select_related("profile")[:8]

    context |= {"top3": top3, "following_users": following_users}
    return render(request, "images/ranking.html", context)
