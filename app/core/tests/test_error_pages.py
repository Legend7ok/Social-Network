import pytest
from django.template import loader
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_unknown_address_gets_the_projects_own_404(client):
    response = client.get("/no-such-page/")

    assert response.status_code == 404
    assert b"Page not found" in response.content


@pytest.mark.django_db
def test_the_404_page_carries_the_navbar(client):
    """It is an ordinary page of the site, so it offers the same way out as the
    rest — a guest arriving on a dead link is not left on a bare screen."""
    response = client.get("/no-such-page/")

    assert b"<header" in response.content


def test_the_500_page_renders_without_a_request():
    """Django renders this one with no request and no context processors, and
    it is shown when something has already broken — so it must not reach for
    anything that could break again."""
    html = loader.get_template("500.html").render()

    assert "Something went wrong" in html


@pytest.mark.django_db
def test_a_form_without_a_csrf_token_gets_the_projects_own_page():
    """A page left open too long, not an attack: the answer says so in words
    instead of explaining the protection."""
    strict_client = Client(enforce_csrf_checks=True)

    response = strict_client.post(
        reverse("login"), {"username": "alice", "password": "testpass123"}
    )

    assert response.status_code == 403
    assert b"This page has expired" in response.content
