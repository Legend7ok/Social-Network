from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login, views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import RedirectURLMixin
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, IntegerField, Subquery, OuterRef, Sum
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import FormView
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


# The views in this project are functions; these two are the exception. Signing
# in extends Django's own LoginView — writing it as a function would mean
# copying its handling of CSRF, caching, the next parameter and the axes hooks —
# and the sign-up view stays a class to match the page it shares.
class LoginView(auth_views.LoginView):
    """Signing in and signing up share one page, so each view renders the other
    side's blank form alongside its own."""

    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["login_form"] = context["form"]
        context.setdefault("register_form", UserRegistrationForm())
        return context


@method_decorator(
    ratelimit(key="ip", rate="10/h", method="POST", block=True), name="post"
)
class RegisterView(RedirectURLMixin, FormView):
    template_name = "registration/login.html"
    form_class = UserRegistrationForm
    next_page = settings.LOGIN_REDIRECT_URL

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.get_default_redirect_url())
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # The form lives on the login page; nothing to show on its own.
        return redirect("login")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["register_form"] = context["form"]
        context.setdefault("login_form", AuthenticationForm(self.request))
        # Keep the page someone was sent here from across a failed attempt.
        context[self.redirect_field_name] = self.get_redirect_url()
        # Tells the template which of the two panels to open.
        context["show_register"] = True
        return context

    def form_valid(self, form):
        with transaction.atomic():
            new_user = form.save()
            create_action(new_user, "has created an account")

        transaction.on_commit(lambda: send_welcome_email.delay(new_user.id))
        # The account was just created here, so there is nothing to authenticate
        # against; name the backend Django would have used.
        auth_login(
            self.request,
            new_user,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        return redirect(self.get_success_url())


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
