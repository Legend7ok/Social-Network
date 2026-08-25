from datetime import date
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.account.models import Profile
from apps.actions.models import Action
from conftest import MINIMAL_PNG


@pytest.mark.django_db
def test_login_page_loads(client):
    response = client.get(reverse("login"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_logout_requires_post(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("logout"))

    assert response.status_code == 405


@pytest.mark.django_db
def test_logout_post_logs_out(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(reverse("logout"))

    assert response.status_code == 302

    home_response = client.get(reverse("home"))
    assert home_response.status_code == 302


@pytest.mark.django_db
def test_register_creates_profile(client):
    payload = {
        "username": "bob",
        "email": "bob@example.com",
        "password": "Str0ngPassphrase!42",
    }

    response = client.post(reverse("register"), data=payload)

    assert response.status_code == 302
    assert response["Location"] == reverse("home")

    user_model = get_user_model()
    user_obj = user_model.objects.get(username="bob")
    assert Profile.objects.filter(user=user_obj).exists()
    assert client.session["_auth_user_id"] == str(user_obj.pk)
    assert Action.objects.filter(user=user_obj, verb="has created an account").exists()


@pytest.mark.django_db
def test_edit_requires_login(client):
    response = client.get(reverse("edit"))

    assert response.status_code == 302


@pytest.mark.django_db
def test_edit_updates_profile(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    payload = {
        "first_name": "AliceUpdated",
        "last_name": "Smith",
        "email": "alice.updated@example.com",
        "date_of_birth": date(1990, 1, 1),
    }

    response = client.post(reverse("edit"), data=payload)

    assert response.status_code == 302
    assert response["Location"] == reverse("my_profile")

    user_obj.refresh_from_db()
    user_obj.profile.refresh_from_db()

    assert user_obj.first_name == "AliceUpdated"
    assert user_obj.last_name == "Smith"
    assert user_obj.email == "alice.updated@example.com"
    assert user_obj.profile.date_of_birth == date(1990, 1, 1)


# ─── login ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_login_post_valid_credentials_redirects_to_home(client, user):
    user_obj, password = user
    response = client.post(
        reverse("login"), {"username": user_obj.username, "password": password}
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("home")


@pytest.mark.django_db
def test_login_by_email_through_the_page(client, user):
    """The field takes an address as well, and that path runs through a backend
    of our own — worth checking end to end, not only in isolation."""
    user_obj, password = user

    response = client.post(
        reverse("login"), {"username": user_obj.email.upper(), "password": password}
    )

    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(user_obj.pk)


# ─── home ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_home_requires_login(client):
    response = client.get(reverse("home"))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_home_returns_200(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("home"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_home_hides_staff_activity(client, user, second_user, staff_user):
    """With no subscriptions the feed falls back to everyone's activity, which
    is where a staff account used to surface."""
    user_obj, password = user
    other, _ = second_user
    staff, _ = staff_user
    Action.objects.create(user=other, verb="liked an image")
    Action.objects.create(user=staff, verb="liked an image")
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("home"))

    actors = {action.user for action in response.context["actions"]}
    assert other in actors
    assert staff not in actors


# ─── register ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_register_get_redirects_to_the_login_page(client):
    """The sign-up form lives on the login page, so /register/ has nothing of
    its own to show."""
    response = client.get(reverse("register"))
    assert response.status_code == 302
    assert response["Location"] == reverse("login")


@pytest.mark.django_db
def test_register_post_weak_password_shows_errors(client):
    response = client.post(
        reverse("register"),
        {
            "username": "bob",
            "email": "bob@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 200
    assert response.context["register_form"].errors["password"]
    assert not get_user_model().objects.filter(username="bob").exists()


@pytest.mark.django_db
def test_register_survives_losing_the_race_for_an_address(client, user):
    """Two sign-ups on one address can both pass the form check and only then
    reach the database, where the unique index turns the loser away."""
    user_obj, _ = user

    with patch("apps.account.forms.users_with_email") as taken:
        taken.return_value.exists.return_value = False
        response = client.post(
            reverse("register"),
            {
                "username": "bob",
                "email": user_obj.email,
                "password": "Str0ngPassphrase!42",
            },
        )

    assert response.status_code == 200
    assert response.context["register_form"].errors
    assert not get_user_model().objects.filter(username="bob").exists()


@pytest.mark.django_db
def test_register_redirects_authenticated_user(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("register"))

    assert response.status_code == 302
    assert response["Location"] == reverse("home")


@pytest.mark.django_db
def test_register_get_carries_next_to_the_login_page(client):
    response = client.get(reverse("register"), {"next": reverse("user_list")})

    assert response["Location"] == f"{reverse('login')}?next={reverse('user_list')}"


@pytest.mark.django_db
def test_register_response_is_not_cached(client):
    """A filled-in sign-up form must not sit in a cache or come back with the
    browser's back button."""
    response = client.post(
        reverse("register"),
        {"username": "bob", "email": "not-an-address", "password": "x"},
    )

    assert "no-store" in response["Cache-Control"]


@pytest.mark.django_db
def test_login_page_carries_both_forms(client):
    """One page holds sign-in and sign-up, so both forms have to reach it."""
    response = client.get(reverse("login"))

    assert "login_form" in response.context
    assert "register_form" in response.context


@pytest.mark.django_db
def test_failed_registration_opens_the_register_panel(client):
    response = client.post(
        reverse("register"),
        {
            "username": "bob",
            "email": "not-an-address",
            "password": "Str0ngPassphrase!42",
        },
    )

    assert response.context["show_register"] is True


@pytest.mark.django_db
def test_register_returns_to_the_page_that_sent_you(client):
    response = client.post(
        reverse("register"),
        {
            "username": "bob",
            "email": "bob@example.com",
            "password": "Str0ngPassphrase!42",
            "next": reverse("user_list"),
        },
    )

    assert response["Location"] == reverse("user_list")


@pytest.mark.django_db
def test_register_ignores_a_next_pointing_off_the_site(client):
    """Otherwise a crafted link would send a freshly signed-in person away."""
    response = client.post(
        reverse("register"),
        {
            "username": "bob",
            "email": "bob@example.com",
            "password": "Str0ngPassphrase!42",
            "next": "https://evil.example.com/",
        },
    )

    assert response["Location"] == reverse("home")


@pytest.mark.django_db
def test_welcome_email_waits_for_the_transaction(
    client, django_capture_on_commit_callbacks
):
    """Dispatching before the commit races the worker to the new row."""
    with patch("apps.account.views.send_welcome_email.delay") as mock_delay:
        with django_capture_on_commit_callbacks(execute=True):
            client.post(
                reverse("register"),
                {
                    "username": "bob",
                    "email": "bob@example.com",
                    "password": "Str0ngPassphrase!42",
                },
            )
            mock_delay.assert_not_called()

    new_user = get_user_model().objects.get(username="bob")
    mock_delay.assert_called_once_with(new_user.id)


# ─── edit ─────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_edit_post_invalid_form_shows_error_message(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(
        reverse("edit"),
        {"first_name": "Alice", "last_name": "", "email": "not-an-email"},
    )
    assert response.status_code == 200
    msgs = [m.message for m in get_messages(response.wsgi_request)]
    assert any("Error" in m for m in msgs)


@pytest.mark.django_db
def test_edit_does_not_save_twice_on_a_refresh(client, user):
    """A refresh after saving must not repeat the POST, so the save answers
    with a redirect and the browser has nothing to send again."""
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(
        reverse("edit"),
        {"first_name": "Alice", "last_name": "Smith", "email": user_obj.email},
        follow=True,
    )

    assert response.redirect_chain == [(reverse("my_profile"), 302)]
    assert [str(m) for m in response.context["messages"]] == [
        "Profile updated successfully"
    ]


# ─── user_list ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_user_list_requires_login(client):
    response = client.get(reverse("user_list"))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_user_list_returns_200(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("user_list"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_list_puts_the_newest_accounts_first(client, user, make_user):
    viewer, password = user
    older, _ = make_user("older", "older@example.com", "testpass123")
    newer, _ = make_user("newer", "newer@example.com", "testpass123")
    client.login(username=viewer.username, password=password)

    response = client.get(reverse("user_list"))

    listed = list(response.context["users"])
    assert listed.index(newer) < listed.index(older)


@pytest.mark.django_db
def test_user_list_hides_staff_accounts(client, user, second_user, staff_user):
    user_obj, password = user
    other, _ = second_user
    staff, _ = staff_user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("user_list"))

    listed = list(response.context["users"])
    assert other in listed
    assert staff not in listed


# ─── profile ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_user_detail_returns_200(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("user_detail", args=[user_obj.username]))
    assert response.status_code == 200
    assert response.context["profile_user"] == user_obj


@pytest.mark.django_db
def test_my_profile_shows_the_owner_view(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("my_profile"))

    assert response.status_code == 200
    assert response.context["profile_user"] == user_obj
    assert response.context["is_owner"] is True
    assert b"Upload photo" in response.content


@pytest.mark.django_db
def test_own_profile_by_username_shows_the_owner_view(client, user):
    """Both addresses lead to the same view, so reaching your own page the long
    way must not turn you into a visitor of yourself."""
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("user_detail", args=[user_obj.username]))

    assert response.context["is_owner"] is True
    assert b"Upload photo" in response.content


@pytest.mark.django_db
def test_profile_shows_one_page_of_images(client, user):
    from apps.images.models import Image

    user_obj, password = user
    for number in range(13):
        Image.objects.create(
            user=user_obj,
            title=f"Image {number}",
            url=f"https://example.com/{number}.png",
            total_likes=1,
        )
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("my_profile"))

    assert len(response.context["images"]) == 12
    # Both counters describe the whole profile, not the page on screen.
    assert response.context["images_count"] == 13
    assert response.context["total_likes"] == 13


@pytest.mark.django_db
def test_profile_grid_offers_owner_controls_on_your_own_page(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("my_profile"))

    assert reverse("images:edit", args=[image.id]).encode() in response.content
    assert reverse("images:delete", args=[image.id]).encode() in response.content


@pytest.mark.django_db
def test_profile_grid_hides_owner_controls_from_visitors(
    client, second_user, user, image
):
    visitor, password = second_user
    owner, _ = user
    client.login(username=visitor.username, password=password)

    response = client.get(reverse("user_detail", args=[owner.username]))

    assert reverse("images:edit", args=[image.id]).encode() not in response.content
    assert reverse("images:delete", args=[image.id]).encode() not in response.content


@pytest.mark.django_db
def test_profile_next_page_keeps_owner_controls(client, user):
    """The scrolled-in tiles are rendered by a second request, so ownership has
    to travel with it."""
    from apps.images.models import Image

    user_obj, password = user
    for number in range(13):
        Image.objects.create(
            user=user_obj,
            title=f"Image {number}",
            url=f"https://example.com/{number}.png",
        )
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("my_profile"), {"images_only": 1, "page": 2})

    last = Image.objects.order_by("created").first()
    assert reverse("images:delete", args=[last.id]).encode() in response.content


@pytest.mark.django_db
def test_profile_counters_cover_the_whole_profile(client, user, second_user, image):
    from apps.account.models import Contact
    from apps.images.models import Image

    owner, password = user
    other, _ = second_user
    Image.objects.create(
        user=owner, title="Second", url="https://example.com/2.png", total_likes=4
    )
    Contact.objects.create(user_from=other.profile, user_to=owner.profile)
    Contact.objects.create(user_from=owner.profile, user_to=other.profile)
    client.login(username=owner.username, password=password)

    response = client.get(reverse("my_profile"))

    assert response.context["images_count"] == 2
    assert response.context["total_likes"] == 4
    assert response.context["follower_count"] == 1
    assert response.context["following_count"] == 1


@pytest.mark.django_db
def test_profile_counters_are_zero_for_an_empty_profile(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("my_profile"))

    assert response.context["images_count"] == 0
    assert response.context["total_likes"] == 0
    assert response.context["follower_count"] == 0
    assert response.context["following_count"] == 0


@pytest.mark.django_db
def test_profile_never_prints_a_template_comment(client, user, image):
    # Django only strips single-line {# #}; a multi-line one reaches the reader
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("my_profile"))

    assert b"{#" not in response.content


@pytest.mark.django_db
def test_failed_login_never_prints_a_template_comment(client, user):
    user_obj, _ = user

    response = client.post(
        reverse("login"), {"username": user_obj.username, "password": "wrong"}
    )

    assert b"{#" not in response.content


@pytest.mark.django_db
def test_failed_login_says_nothing_about_which_half_was_wrong(client, user):
    """The message must read the same for an unknown account and a wrong
    password, or the page becomes a way to check who is registered here."""
    user_obj, _ = user

    known = client.post(
        reverse("login"), {"username": user_obj.username, "password": "wrong"}
    )
    unknown = client.post(
        reverse("login"), {"username": "nobody@example.com", "password": "wrong"}
    )

    assert b"Wrong email or password." in known.content
    assert b"Wrong email or password." in unknown.content


@pytest.mark.django_db
def test_profile_next_page_returns_the_grid_partial(client, user):
    from apps.images.models import Image

    user_obj, password = user
    for number in range(13):
        Image.objects.create(
            user=user_obj,
            title=f"Image {number}",
            url=f"https://example.com/{number}.png",
        )
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("my_profile"), {"images_only": 1, "page": 2})

    assert len(response.context["images"]) == 1
    assert b"<html" not in response.content


@pytest.mark.django_db
def test_profile_scroll_past_the_last_page_returns_nothing(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("my_profile"), {"images_only": 1, "page": 5})

    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.django_db
def test_someone_elses_profile_shows_the_visitor_view(client, user, second_user):
    user_obj, password = user
    target, _ = second_user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("user_detail", args=[target.username]))

    assert response.context["is_owner"] is False
    # "Change Password" is no proof here: the navbar carries it on every page.
    assert b"Upload photo" not in response.content


@pytest.mark.django_db
def test_user_detail_returns_404_for_unknown_user(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("user_detail", args=["nobody"]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_user_detail_returns_404_for_staff_account(client, user, staff_user):
    user_obj, password = user
    staff, _ = staff_user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("user_detail", args=[staff.username]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_user_detail_renders_following_false_when_not_following(
    client, user, second_user
):
    user_obj, password = user
    target, _ = second_user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("user_detail", args=[target.username]))
    assert b"following: false" in response.content


@pytest.mark.django_db
def test_user_detail_renders_following_true_when_following(client, user, second_user):
    from apps.account.models import Contact

    user_obj, password = user
    target, _ = second_user
    Contact.objects.create(user_from=user_obj.profile, user_to=target.profile)
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("user_detail", args=[target.username]))
    assert b"following: true" in response.content


@pytest.mark.django_db
def test_profile_photo_update_saves_valid_photo(
    client, user, django_capture_on_commit_callbacks
):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    photo = SimpleUploadedFile("avatar.png", MINIMAL_PNG, content_type="image/png")
    with (
        patch("PIL.Image.open"),
        django_capture_on_commit_callbacks(execute=False),
    ):
        response = client.post(reverse("profile_photo"), {"photo": photo})
    assert response.status_code == 302
    user_obj.profile.refresh_from_db()
    assert user_obj.profile.photo


@pytest.mark.django_db
def test_profile_photo_update_rejects_oversized(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    big = b"\x89PNG" + b"x" * (settings.MAX_UPLOAD_SIZE + 1)
    big_file = SimpleUploadedFile("big.png", big, content_type="image/png")
    client.post(reverse("profile_photo"), {"photo": big_file})
    user_obj.profile.refresh_from_db()
    assert not user_obj.profile.photo


@pytest.mark.django_db
def test_profile_photo_update_rejects_invalid_extension(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    gif_file = SimpleUploadedFile("avatar.gif", b"GIF89a", content_type="image/gif")
    client.post(reverse("profile_photo"), {"photo": gif_file})
    user_obj.profile.refresh_from_db()
    assert not user_obj.profile.photo
