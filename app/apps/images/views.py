from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django_ratelimit.decorators import ratelimit

User = get_user_model()

from .forms import ImageBookmarkForm, ImageUploadForm
from .models import Image
from .services import (
    record_image_view,
    get_image_ranking,
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
    image = get_object_or_404(Image, id=id, slug=slug)
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

    return render(
        request,
        "images/image/detail.html",
        {"section": "images", "image": image, "total_views": total_views},
    )


@login_required
def image_list(request):
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
    return render(request, "images/image/_image_status.html", {"image": image})


@login_required()
def image_ranking(request):
    ranking = cache.get(settings.IMAGE_RANKING_CACHE_KEY)
    if ranking is None:
        image_ranking_ids = get_image_ranking()
        images_by_id = {
            image.id: image
            for image in Image.objects.filter(id__in=image_ranking_ids).select_related("user", "user__profile")
        }
        ranking = [images_by_id[id] for id in image_ranking_ids if id in images_by_id]
        cache.set(settings.IMAGE_RANKING_CACHE_KEY, ranking, settings.IMAGE_RANKING_CACHE_TTL)

    views_map = get_images_views([img.id for img in ranking])
    for img in ranking:
        img.total_views = views_map.get(img.id, 0)

    following_users = (
        User.objects.filter(profile__in=request.user.profile.following.all())
        .select_related("profile")[:8]
    )

    return render(
        request,
        "images/image/ranking.html",
        {"section": "images", "ranking": ranking, "following_users": following_users},
    )
