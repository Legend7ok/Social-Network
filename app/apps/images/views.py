from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django_ratelimit.decorators import ratelimit

from .forms import ImageCreateForm
from .models import Image
from .services import record_image_view, get_image_ranking
from .tasks import download_image
from apps.actions.utils import create_action


def bookmarklet_launcher(request):
    js = render(request, "bookmarklet_launcher.js", {"site_url": settings.SITE_URL})
    return HttpResponse(js, content_type="application/javascript")


@login_required
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def image_create(request):
    if request.method == "POST":
        form = ImageCreateForm(request.POST)
        if form.is_valid():
            new_image = form.save(commit=False)
            new_image.user = request.user
            new_image.save()
            download_image.delay(new_image.id, new_image.url)
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
    most_viewed = cache.get(settings.IMAGE_RANKING_CACHE_KEY)
    if most_viewed is None:
        image_ranking_ids = get_image_ranking()
        images_by_id = {
            image.id: image for image in Image.objects.filter(id__in=image_ranking_ids)
        }
        most_viewed = [
            images_by_id[id] for id in image_ranking_ids if id in images_by_id
        ]
        cache.set(
            settings.IMAGE_RANKING_CACHE_KEY,
            most_viewed,
            settings.IMAGE_RANKING_CACHE_TTL,
        )

    return render(
        request,
        "images/image/ranking.html",
        {"section": "images", "most_viewed": most_viewed},
    )
