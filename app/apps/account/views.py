from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_lockout_response, get_credentials as axes_get_credentials

from .forms import LoginForm, UserRegistrationForm, UserEditForm, ProfileEditForm
from .tasks import send_welcome_email
from .models import Profile, Contact
from apps.actions.utils import create_action
from apps.actions.models import Action
from core.utils import toggle_action

User = get_user_model()


def user_login(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            credentials = axes_get_credentials(username=cd["username"])
            if not AxesProxyHandler.is_allowed(request, credentials):
                return get_lockout_response(request, credentials=credentials)
            user = authenticate(
                request, username=cd["username"], password=cd["password"]
            )
            if user is not None:
                if user.is_active:
                    login(request, user)
                    messages.success(request, "Authenticated successfully")
                    return redirect("dashboard")
                else:
                    messages.error(request, "Your account has been disabled")
            else:
                messages.error(request, "Invalid username or password")

    else:
        form = LoginForm()

    return render(request, "account/login.html", {"form": form})


@login_required
def dashboard(request):
    cache_key = f"dashboard_{request.user.id}"
    actions = cache.get(cache_key)
    if actions is None:
        actions_qs = Action.objects.exclude(user=request.user)
        following_ids = request.user.profile.following.values_list("user_id", flat=True)
        if following_ids:
            actions_qs = actions_qs.filter(user_id__in=following_ids)
        actions = list(
            actions_qs.select_related("user", "user__profile").prefetch_related("target")[:10]
        )
        cache.set(cache_key, actions, settings.DASHBOARD_CACHE_TTL)

    return render(
        request,
        "account/dashboard.html",
        {"section": "dashboard", "actions": actions, "site_url": settings.SITE_URL},
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
    users = User.objects.filter(is_active=True)
    return render(
        request, "account/user/list.html", {"section": "people", "users": users}
    )


@login_required
def user_detail(request, username):
    user = get_object_or_404(User, username=username, is_active=True)
    return render(
        request, "account/user/detail.html", {"section": "people", "user": user}
    )


@require_POST
@login_required
@ratelimit(key="user", rate="20/m", block=True)
def user_follow(request):
    def add(user):
        Contact.objects.get_or_create(
            user_from=request.user.profile, user_to=user.profile
        )
        create_action(request.user, "is following", user)

    def remove(user):
        Contact.objects.filter(
            user_from=request.user.profile, user_to=user.profile
        ).delete()

    return toggle_action(request, User, "follow", add, remove)
