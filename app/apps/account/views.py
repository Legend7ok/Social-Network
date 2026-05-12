from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, IntegerField, Subquery, OuterRef, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django_ratelimit.decorators import ratelimit

from apps.images.models import Image

from .forms import UserRegistrationForm, UserEditForm, ProfileEditForm
from .tasks import send_welcome_email
from .models import Profile
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
        cache.set(cache_key, actions, settings.DASHBOARD_CACHE_TTL)

    following_users = (
        User.objects.filter(profile__in=request.user.profile.following.all())
        .select_related("profile")[:8]
    )

    return render(
        request,
        "account/home.html",
        {
            "section": "home",
            "actions": actions,
            "site_url": settings.SITE_URL,
            "following_users": following_users,
        },
    )


@ratelimit(key="ip", rate="10/h", method="POST", block=True)
def register(request):
    if request.method == "POST":
        user_form = UserRegistrationForm(request.POST)
        if user_form.is_valid():
            with transaction.atomic():
                new_user = user_form.save(commit=False)
                new_user.set_password(user_form.cleaned_data["password"])
                new_user.save()

                Profile.objects.create(user=new_user)
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
def user_list(request):
    filter_type = request.GET.get("filter", "all")
    my_profile = request.user.profile

    if filter_type == "following":
        base_qs = User.objects.filter(profile__in=my_profile.following.all())
    elif filter_type == "followers":
        base_qs = User.objects.filter(profile__in=my_profile.followers.all())
    else:
        base_qs = User.objects.filter(is_active=True).exclude(id=request.user.id)

    image_likes = (
        Image.objects.filter(user=OuterRef("pk"))
        .values("user")
        .annotate(s=Sum("total_likes"))
        .values("s")
    )

    users = (
        base_qs.select_related("profile")
        .annotate(
            images_count=Count("images", distinct=True),
            followers_count=Count("profile__followers", distinct=True),
            total_likes=Coalesce(
                Subquery(image_likes, output_field=IntegerField()), 0
            ),
        )
        .order_by("first_name", "last_name")
    )

    following_ids = set(my_profile.following.values_list("user_id", flat=True))

    return render(
        request,
        "account/user/list.html",
        {
            "section": "people",
            "users": users,
            "filter": filter_type,
            "following_ids": following_ids,
        },
    )


@login_required
def user_detail(request, username):
    user = get_object_or_404(User, username=username, is_active=True)
    return render(
        request, "account/user/detail.html", {"section": "people", "user": user}
    )
