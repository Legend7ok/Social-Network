from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django_ratelimit.decorators import ratelimit

from apps.account.selectors import with_card_counters
from apps.images.services import apply_live_views

from .selectors import search_images, search_users

TABS = ("images", "people")


def normalize_query(raw):
    # Postgres rejects NUL bytes outright, and a huge string would be pushed
    # into a tsquery and into three similarity() calls per row.
    return raw.replace("\x00", "").strip()[: settings.SEARCH_MAX_QUERY_LENGTH]


@login_required
@ratelimit(key="user", rate=settings.SEARCH_RATE, method="GET", block=True)
def search(request):
    query = normalize_query(request.GET.get("q", ""))
    chosen_tab = request.GET.get("tab")
    if chosen_tab not in TABS:
        chosen_tab = None
    # Scroll requests come from the card partials shared with the images and
    # people lists, so each tab arrives with its own flag.
    results_only = request.GET.get("images_only") or request.GET.get("users_only")

    context = {
        "q": query,
        "min_query_length": settings.SEARCH_MIN_QUERY_LENGTH,
    }

    if len(query) < settings.SEARCH_MIN_QUERY_LENGTH:
        if results_only:
            return HttpResponse("")
        context["query_too_short"] = bool(query)
        return render(request, "search/results.html", context)

    images = search_images(query)
    people = search_users(query)
    images_count = images.count()
    people_count = people.count()
    context["images_count"] = images_count
    context["people_count"] = people_count

    # Without an explicit choice, open the tab that actually has results.
    tab = chosen_tab or ("people" if people_count > images_count else "images")
    context["tab"] = tab

    if tab == "people":
        queryset, per_page = with_card_counters(people), settings.SEARCH_PEOPLE_PER_PAGE
    else:
        queryset, per_page = images, settings.SEARCH_IMAGES_PER_PAGE

    paginator = Paginator(queryset, per_page)
    try:
        results = paginator.page(request.GET.get("page"))
    except PageNotAnInteger:
        results = paginator.page(1)
    except EmptyPage:
        if results_only:
            return HttpResponse("")
        results = paginator.page(paginator.num_pages)

    if tab == "people":
        context["users"] = results
        context["following_ids"] = set(
            request.user.profile.following.values_list("user_id", flat=True)
        )
        partial = "search/partials/people_results.html"
    else:
        # Force evaluation so total_views attrs survive template iteration
        results.object_list = list(results.object_list)
        apply_live_views(results.object_list)
        context["images"] = results
        partial = "search/partials/image_results.html"

    if results_only:
        return render(request, partial, context)

    return render(request, "search/results.html", context)
