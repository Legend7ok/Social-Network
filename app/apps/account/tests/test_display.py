import pytest
from django.contrib.auth.models import AnonymousUser

from apps.account.display import display_name, initials
from apps.account.templatetags import user_display


@pytest.mark.django_db
def test_display_name_prefers_the_real_name(user):
    user_obj, _ = user
    user_obj.first_name = "Alice"
    user_obj.last_name = "Smith"

    assert display_name(user_obj) == "Alice Smith"


@pytest.mark.django_db
def test_display_name_falls_back_to_the_username(user):
    """Registration asks for a username only, so most accounts have no name."""
    user_obj, _ = user

    assert display_name(user_obj) == user_obj.username


@pytest.mark.django_db
def test_initials_come_from_the_name_when_there_is_one(user):
    user_obj, _ = user
    user_obj.first_name = "alice"
    user_obj.last_name = "smith"

    assert initials(user_obj) == "AS"


@pytest.mark.django_db
def test_initials_fall_back_to_the_username(user):
    """The avatar placeholder must never come out empty."""
    user_obj, _ = user

    assert initials(user_obj) == user_obj.username[:2].upper()


@pytest.mark.django_db
def test_initials_use_a_first_name_on_its_own(user):
    user_obj, _ = user
    user_obj.first_name = "Alice"

    assert initials(user_obj) == "A"


# ─── filters ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("visitor", [AnonymousUser(), ""])
def test_filters_render_nothing_for_a_missing_person(visitor):
    """A signed-out visitor on a public page, and a podium place with no image
    behind it, both reach these filters — neither may bring the page down."""
    assert user_display.display_name(visitor) == ""
    assert user_display.initials(visitor) == ""
