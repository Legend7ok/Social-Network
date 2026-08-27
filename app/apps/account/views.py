import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login, views as auth_views
from django.contrib.auth.decorators import login_not_required, login_required
from django.contrib.auth.views import RedirectURLMixin, redirect_to_login
from django.db import IntegrityError, transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect, resolve_url
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST
from django.views.generic import FormView
from django.utils import timezone
from django_ratelimit.decorators import ratelimit

from apps.images.services import apply_live_views

from .selectors import (
    public_users,
    sidebar_following,
    with_card_counters,
    with_profile_counters,
)
from .forms import (
    EmailOrUsernameAuthenticationForm,
    UserRegistrationForm,
    UserEditForm,
    ProfileEditForm,
    ProfilePhotoForm,
)
from .tasks import send_welcome_email
from apps.actions.models import Action
from apps.actions.selectors import feed
from apps.actions.utils import create_action

User = get_user_model()

logger = logging.getLogger(__name__)

# Fits the profile grid exactly: three columns up to tablets, four from xl up.
PROFILE_IMAGES_PER_PAGE = 12


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
    # Everyone's activity, whoever you follow. Narrowing the feed to your own
    # subscriptions emptied it on the first follow, and an open feed is what
    # gives a new account something to follow in the first place.
    actions = feed(request.user)[:10]

    following_users = sidebar_following(request.user)

    return render(
        request,
        "account/home.html",
        {
            "actions": actions,
            "following_users": following_users,
            # The cards tell one kind of entry from another by verb; this hands
            # the template the same names the rest of the code uses.
            "verbs": Action.Verb,
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
    form_class = EmailOrUsernameAuthenticationForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["login_form"] = context["form"]
        context["register_form"] = UserRegistrationForm()
        return context


# The same guards Django puts on its own LoginView: keep the password out of
# error reports, keep the filled-in form out of caches and the back button, and
# stay reachable if the project ever puts the whole site behind a login.
@method_decorator(
    [login_not_required, sensitive_post_parameters(), never_cache], name="dispatch"
)
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
        # The form lives on the login page; nothing to show on its own. Carry
        # the page they were sent from along, or it is lost on the way there.
        redirect_to = self.get_redirect_url()
        if not redirect_to:
            return redirect("login")
        return redirect_to_login(
            redirect_to, resolve_url("login"), self.redirect_field_name
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["register_form"] = context["form"]
        context["login_form"] = EmailOrUsernameAuthenticationForm(self.request)
        # Keep the page someone was sent here from across a failed attempt.
        context[self.redirect_field_name] = self.get_redirect_url()
        # Tells the template which of the two panels to open.
        context["show_register"] = True
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                new_user = form.save()
                create_action(new_user, Action.Verb.CREATED_ACCOUNT)
        except IntegrityError:
            # The form found the name and address free, then someone else took
            # one of them before this row reached the table.
            logger.warning("register: lost the race for %s", form.data.get("username"))
            form.add_error(
                None, "That username or address was just taken. Please try again."
            )
            return self.form_invalid(form)

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
            # Answering a successful POST with a page means refreshing it asks
            # the browser to send the form again; a redirect ends the request.
            return redirect("my_profile")

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

    people = public_users()
    if filter_type == "following":
        base_qs = people.filter(profile__in=viewer_profile.following.all())
    elif filter_type == "followers":
        base_qs = people.filter(profile__in=viewer_profile.followers.all())
    else:
        base_qs = people.exclude(id=request.user.id)

    users_qs = (
        with_card_counters(base_qs)
        # Newest first. Sorting by name put every nameless account on top, and
        # sign-up stopped asking for a name, so that was most of them. The id
        # breaks ties: equal keys leave the order to the database, and pages
        # would then repeat one person and skip another.
        .order_by("-date_joined", "id")
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
        "users": users,
        "filter": filter_type,
        "following_ids": following_ids,
    }

    if users_only:
        return render(request, "account/partials/user_cards.html", context)

    return render(request, "account/users/list.html", context)


@login_required
def profile(request, username=None):
    """Both /me/ and /users/<username>/. The two pages differed only in the
    photo upload and the buttons, so ownership is a flag rather than a view of
    its own. No username means the viewer is looking at themselves — service
    accounts are hidden from everyone else, but not from their own owner.

    The context name is profile_user, not user: that one already belongs to the
    signed-in person and shadowing it would hand templates the wrong human.
    """
    if username is None:
        people = User.objects.filter(pk=request.user.pk)
    else:
        people = public_users().filter(username=username)
    profile_user = get_object_or_404(
        with_profile_counters(people, request.user).select_related("profile")
    )
    is_owner = profile_user == request.user
    images_only = request.GET.get("images_only")

    paginator = Paginator(
        profile_user.images.order_by("-created"), PROFILE_IMAGES_PER_PAGE
    )
    try:
        images = paginator.page(request.GET.get("page"))
    except PageNotAnInteger:
        images = paginator.page(1)
    except EmptyPage:
        if images_only:
            return HttpResponse("")
        images = paginator.page(paginator.num_pages)

    # Force evaluation so total_views attrs survive template iteration
    images.object_list = list(images.object_list)
    apply_live_views(images.object_list)

    if images_only:
        return render(
            request,
            "account/partials/profile_images.html",
            {"images": images, "is_owner": is_owner},
        )

    followers = (
        public_users()
        .filter(profile__in=profile_user.profile.followers.all())
        .select_related("profile")[:4]
    )
    following = (
        public_users()
        .filter(profile__in=profile_user.profile.following.all())
        .select_related("profile")[:4]
    )

    return render(
        request,
        "account/profile.html",
        {
            "profile_user": profile_user,
            "is_owner": is_owner,
            "images": images,
            # All four came with the person, counted over everything they have
            # rather than over the page on screen.
            "images_count": profile_user.images_count,
            "total_likes": profile_user.total_likes,
            "is_following": profile_user.followed_by_viewer,
            "followers": followers,
            "following": following,
            "follower_count": profile_user.followers_count,
            "following_count": profile_user.following_count,
        },
    )
