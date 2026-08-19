from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, IntegerField, Subquery, OuterRef, Sum
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.utils import timezone
from django_ratelimit.decorators import ratelimit

from apps.images.models import Image
from apps.images.services import get_images_views

from .forms import (
    UserRegistrationForm,
    UserEditForm,
    ProfileEditForm,
    ProfilePhotoForm,
)
from .tasks import send_welcome_email
from apps.actions.utils import create_action
from apps.actions.models import Action

User = get_user_model()


def lockout_view(request, credentials, *args, **kwargs):
    stored = request.session.get("lockout_until")
    if stored:
        lockout_until = timezone.datetime.fromisoformat(stored)
        if lockout_until <= timezone.now():
            stored = None
    if not stored:
        lockout_until = timezone.now() + settings.AXES_COOLOFF_TIME
        request.session["lockout_until"] = lockout_until.isoformat()
    return render(
        request,
        "account/lockout.html",
        {"lockout_until": lockout_until.isoformat()},
        status=429,
    )


@login_required
def home(request):
    cache_key = f"home_{request.user.id}"
    actions = cache.get(cache_key)
    if actions is None:
        actions_qs = Action.objects.exclude(user=request.user)
        following_ids = request.user.profile.following.values_list("user_id", flat=True)
        if following_ids:
            actions_qs = actions_qs.filter(user_id__in=following_ids)
        actions = list(
            actions_qs.select_related("user", "user__profile").prefetch_related(
                "target"
            )[:10]
        )
        cache.set(cache_key, actions, settings.HOME_CACHE_TTL)

    following_users = User.objects.filter(
        profile__in=request.user.profile.following.all()
    ).select_related("profile")[:8]

    return render(
        request,
        "account/home.html",
        {
            "section": "home",
            "actions": actions,
            "following_users": following_users,
        },
    )


@ratelimit(key="ip", rate="10/h", method="POST", block=True)
def register(request):
    if request.method == "POST":
        user_form = UserRegistrationForm(request.POST)
        if user_form.is_valid():
            with transaction.atomic():
                new_user = user_form.save()
                create_action(new_user, "has created an account")

            send_welcome_email.delay(new_user.id)
            return render(request, "account/register_done.html", {"new_user": new_user})
    else:
        user_form = UserRegistrationForm()

    return render(request, "account/register.html", {"user_form": user_form})


@login_required
def edit(request):
    if request.method == "POST":
        user_form = UserEditForm(instance=request.user, data=request.POST)
        profile_form = ProfileEditForm(
            instance=request.user.profile, data=request.POST, files=request.FILES
        )

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully")
        else:
            messages.error(request, "Error updating your profile")

    else:
        user_form = UserEditForm(instance=request.user)
        profile_form = ProfileEditForm(instance=request.user.profile)

    return render(
        request,
        "account/edit.html",
        {"user_form": user_form, "profile_form": profile_form},
    )


@login_required
def my_profile(request):
    profile = request.user.profile
    images = list(request.user.images.order_by("-created"))
    views_map = get_images_views([img.id for img in images])
    for img in images:
        img.total_views = views_map.get(img.id, 0)

    total_likes = sum(img.total_likes for img in images)

    follower_profiles = profile.followers.all()
    following_profiles = profile.following.all()

    followers = User.objects.filter(profile__in=follower_profiles).select_related(
        "profile"
    )[:4]
    following = User.objects.filter(profile__in=following_profiles).select_related(
        "profile"
    )[:4]

    return render(
        request,
        "account/my_profile.html",
        {
            "section": "people",
            "profile": profile,
            "images": images,
            "total_likes": total_likes,
            "followers": followers,
            "following": following,
            "follower_count": follower_profiles.count(),
            "following_count": following_profiles.count(),
        },
    )


@login_required
@require_POST
def profile_photo_update(request):
    form = ProfilePhotoForm(
        instance=request.user.profile, data=request.POST, files=request.FILES
    )
    if form.is_valid():
        form.save()
        messages.success(request, "Photo updated successfully")
    else:
        messages.error(request, form.errors.get("photo", ["Invalid photo"])[0])
    return redirect("my_profile")


@login_required
def user_list(request):
    filter_type = request.GET.get("filter", "all")
    users_only = request.GET.get("users_only")
    viewer_profile = request.user.profile

    if filter_type == "following":
        base_qs = User.objects.filter(profile__in=viewer_profile.following.all())
    elif filter_type == "followers":
        base_qs = User.objects.filter(profile__in=viewer_profile.followers.all())
    else:
        base_qs = User.objects.filter(is_active=True).exclude(id=request.user.id)

    image_likes = (
        Image.objects.filter(user=OuterRef("pk"))
        .values("user")
        .annotate(s=Sum("total_likes"))
        .values("s")
    )

    users_qs = (
        base_qs.select_related("profile")
        .annotate(
            images_count=Count("images", distinct=True),
            followers_count=Count("profile__followers", distinct=True),
            total_likes=Coalesce(Subquery(image_likes, output_field=IntegerField()), 0),
        )
        .order_by("first_name", "last_name")
    )

    paginator = Paginator(users_qs, 10)
    page = request.GET.get("page")
    try:
        users = paginator.page(page)
    except PageNotAnInteger:
        users = paginator.page(1)
    except EmptyPage:
        if users_only:
            return HttpResponse("")
        users = paginator.page(paginator.num_pages)

    following_ids = set(viewer_profile.following.values_list("user_id", flat=True))

    context = {
        "section": "people",
        "users": users,
        "filter": filter_type,
        "following_ids": following_ids,
    }

    if users_only:
        return render(request, "account/partials/user_cards.html", context)

    return render(request, "account/users/list.html", context)


@login_required
def user_detail(request, username):
    profile_user = get_object_or_404(
        User.objects.select_related("profile"),
        username=username,
        is_active=True,
    )

    images = list(profile_user.images.order_by("-created"))
    views_map = get_images_views([img.id for img in images])
    for img in images:
        img.total_views = views_map.get(img.id, 0)

    total_likes = sum(img.total_likes for img in images)

    follower_profiles = profile_user.profile.followers.all()
    following_profiles = profile_user.profile.following.all()

    is_following = follower_profiles.filter(user=request.user).exists()

    followers = User.objects.filter(profile__in=follower_profiles).select_related(
        "profile"
    )[:4]
    following = User.objects.filter(profile__in=following_profiles).select_related(
        "profile"
    )[:4]

    return render(
        request,
        "account/users/detail.html",
        {
            "section": "people",
            "user": profile_user,
            "images": images,
            "total_likes": total_likes,
            "is_following": is_following,
            "followers": followers,
            "following": following,
            "follower_count": follower_profiles.count(),
            "following_count": following_profiles.count(),
        },
    )
