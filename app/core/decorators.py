from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


def login_required_for_htmx(view):
    """`login_required` that answers htmx with 401 instead of a redirect.

    A redirect is followed inside the request htmx made, so a session that ran
    out while the page stayed open put the whole sign-in page in the middle of
    it, where a comment was meant to go. htmx swaps nothing in for a 401, and
    the page says in words that the session is over. A plain form is still
    sent to sign in, the way `login_required` always did.
    """
    sign_in_first = login_required(view)

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if (
            not request.user.is_authenticated
            and request.headers.get("HX-Request") == "true"
        ):
            return HttpResponse(status=401)
        return sign_in_first(request, *args, **kwargs)

    return wrapper
