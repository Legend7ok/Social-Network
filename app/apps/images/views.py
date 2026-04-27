from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .forms import ImageCreateForm
from .models import Image
from .services import record_image_view, get_image_ranking
from apps.actions.utils import create_action
from core.utils import toggle_action


def bookmarklet_launcher(request):
    js = render(request, "bookmarklet_launcher.js", {"site_url": settings.SITE_URL})
    return HttpResponse(js, content_type="application/javascript")


@login_required
def image_create(request):
    if request.method == "POST":
        form = ImageCreateForm(request.POST)
        if form.is_valid():
            new_image = form.save(commit=False)
            new_image.user = request.user
            new_image.save()
            create_action(request.user, "bookmarked image", new_image)
            messages.success(request, "Image added successfully")
            return redirect(new_image.get_absolute_url())
    else:
        form = ImageCreateForm(data=request.GET)

    return render(
        request, "images/image/create.html", {"section": "images", "form": form}
    )


def image_detail(request, id, slug):
    image = get_object_or_404(Image, id=id, slug=slug)
    total_views = record_image_view(image.id)

    return render(
        request,
        "images/image/detail.html",
        {"section": "images", "image": image, "total_views": total_views},
    )


@login_required
@require_POST
def image_like(request):
    def add(image):
        image.users_like.add(request.user)
        create_action(request.user, "likes", image)

    def remove(image):
        image.users_like.remove(request.user)

    return toggle_action(request, Image, "like", add, remove)


@login_required()
def image_list(request):
    images = Image.objects.all()
    paginator = Paginator(images, 8)
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

    if images_only:
        return render(
            request,
            "images/image/list_images.html",
            {"section": "images", "images": images},
        )

    return render(
        request, "images/image/list.html", {"section": "images", "images": images}
    )


@login_required()
def image_ranking(request):
    image_ranking_ids = get_image_ranking()
    images_by_id = {image.id: image for image in Image.objects.filter(id__in=image_ranking_ids)}
    most_viewed = [images_by_id[id] for id in image_ranking_ids if id in images_by_id]

    return render(
        request,
        "images/image/ranking.html",
        {"section": "images", "most_viewed": most_viewed},
    )
