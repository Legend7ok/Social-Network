from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django_ratelimit.decorators import ratelimit

User = get_user_model()

from .forms import ImageBookmarkForm, ImageUploadForm
from .models import Image
from .services import (
    record_image_view,
    get_image_ranking,
    get_image_ranking_count,
    get_image_views,
    get_images_views,
    is_first_view,
)
from .tasks import download_image
from apps.actions.utils import create_action


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

    return render(
        request, "images/image/create.html", {"section": "images", "form": form}
    )


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
            total_views = record_image_view(image.id)
        else:
            total_views = get_image_views(image.id)
    else:
        total_views = 0

    users_like = image.users_like.select_related("profile").all()

    following_users = (
        User.objects.filter(profile__in=request.user.profile.following.all())
        .select_related("profile")[:8]
        if request.user.is_authenticated else []
    )

    return render(
        request,
        "images/image/detail.html",
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
        images = Image.objects.filter(user=request.user).select_related("user", "user__profile")
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

    following_users = (
        User.objects.filter(profile__in=request.user.profile.following.all())
        .select_related("profile")[:8]
    )

    context = {
        "section": "images",
        "images": images,
        "following_users": following_users,
        "mine": mine,
    }

    if images_only:
        return render(request, "images/partials/image_cards.html", context)

    return render(request, "images/image/list.html", context)


@login_required
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def image_upload(request):
    if request.method == "POST":
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            new_image = form.save(commit=False)
            new_image.user = request.user
            new_image.save()
            create_action(request.user, "uploaded image", new_image)
            messages.success(request, "Image uploaded successfully")
            return redirect(new_image.get_absolute_url())
    else:
        form = ImageUploadForm()
    return render(
        request, "images/image/upload.html", {"section": "images", "form": form}
    )


def image_status(request, id):
    image = get_object_or_404(Image, id=id)
    return render(request, "images/partials/image_status.html", {"image": image})


@login_required()
def image_ranking(request):
    per_page = 10
    ranking_only = request.GET.get("ranking_only")

    try:
        page = int(request.GET.get("page", 1))
    except ValueError:
        page = 1

    list_start = 3 + (page - 1) * per_page

    # Fetch current list page from Redis + DB
    list_ids = get_image_ranking(start=list_start, count=per_page)
    list_images_by_id = {
        img.id: img
        for img in Image.objects.filter(id__in=list_ids).select_related("user", "user__profile")
    }
    ranking_list = []
    for i, img_id in enumerate(list_ids, start=list_start + 1):
        if img_id in list_images_by_id:
            img = list_images_by_id[img_id]
            img.rank = i
            ranking_list.append(img)

    views_map = get_images_views([img.id for img in ranking_list])
    for img in ranking_list:
        img.total_views = views_map.get(img.id, 0)

    total = get_image_ranking_count()
    has_next = (list_start + per_page) < total
    next_page = page + 1

    if ranking_only:
        return render(request, "images/partials/ranking_rows.html", {
            "ranking_list": ranking_list,
            "has_next": has_next,
            "next_page": next_page,
        })

    # Top 3 only needed for full page load
    top3_ids = get_image_ranking(start=0, count=3)
    top3_by_id = {
        img.id: img
        for img in Image.objects.filter(id__in=top3_ids).select_related("user", "user__profile")
    }
    top3_views = get_images_views(top3_ids)
    top3 = []
    for i, img_id in enumerate(top3_ids, start=1):
        if img_id in top3_by_id:
            img = top3_by_id[img_id]
            img.rank = i
            img.total_views = top3_views.get(img_id, 0)
            top3.append(img)

    following_users = (
        User.objects.filter(profile__in=request.user.profile.following.all())
        .select_related("profile")[:8]
    )

    return render(request, "images/image/ranking.html", {
        "section": "images",
        "top3": top3,
        "ranking_list": ranking_list,
        "has_next": has_next,
        "next_page": next_page,
        "following_users": following_users,
    })
