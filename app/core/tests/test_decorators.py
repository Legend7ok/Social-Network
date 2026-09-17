from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory

from core.decorators import login_required_for_htmx


@login_required_for_htmx
def private_view(request):
    return HttpResponse("inside")


def request_from(user, **headers):
    request = RequestFactory().post("/somewhere/", **headers)
    request.user = user
    return request


def test_htmx_without_a_session_is_refused_rather_than_redirected():
    """The redirect would be followed inside the request, and the sign-in page
    would be swapped into the middle of the page that made it."""
    response = private_view(request_from(AnonymousUser(), HTTP_HX_REQUEST="true"))

    assert response.status_code == 401


def test_a_plain_request_without_a_session_is_still_sent_to_sign_in():
    response = private_view(request_from(AnonymousUser()))

    assert response.status_code == 302
    assert "/login/" in response.url


def test_a_signed_in_request_reaches_the_view(django_user_model, db):
    person = django_user_model.objects.create_user("dave", "dave@example.com", "pw")

    response = private_view(request_from(person, HTTP_HX_REQUEST="true"))

    assert response.content == b"inside"
