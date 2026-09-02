import pytest
from unittest.mock import MagicMock, patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.images.forms import ImageBookmarkForm, ImageEditForm, ImageUploadForm
from apps.images.models import Image
from apps.images.views import (
    LIKED_BY_LIMIT,
    STATUS_POLL_LIMIT,
    STATUS_POLL_SLOWDOWN,
)
from apps.images.services import record_image_view
from conftest import MINIMAL_PNG, png_bytes


# ─── Model Tests ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_image_str(image):
    assert str(image) == "Test Image"


@pytest.mark.django_db
def test_image_slug_auto_generated_from_title(image):
    assert image.slug == "test-image"


@pytest.mark.django_db
def test_image_slug_follows_the_title(user):
    user_obj, _ = user
    img_file = SimpleUploadedFile("test.png", MINIMAL_PNG, content_type="image/png")
    img = Image.objects.create(
        user=user_obj,
        title="Test Image",
        slug="my-custom-slug",
        url="https://example.com/test.png",
        image=img_file,
    )
    assert img.slug == "test-image"


@pytest.mark.django_db
def test_image_slug_is_rebuilt_when_the_title_changes(image):
    image.title = "Renamed Image"
    image.save()

    image.refresh_from_db()
    assert image.slug == "renamed-image"


@pytest.mark.django_db
def test_image_slug_falls_back_when_the_title_has_no_letters(user):
    user_obj, _ = user
    img = Image.objects.create(
        user=user_obj, title="🔥🔥🔥", url="https://example.com/fire.png"
    )
    assert img.slug == "image"
    assert img.get_absolute_url()


@pytest.mark.django_db
def test_image_get_absolute_url(image):
    expected = reverse("images:detail", args=[image.id, image.slug])
    assert image.get_absolute_url() == expected


@pytest.mark.django_db
def test_image_ordering_newest_first(user):
    user_obj, _ = user
    for i in range(3):
        img_file = SimpleUploadedFile(
            f"img{i}.png", MINIMAL_PNG, content_type="image/png"
        )
        Image.objects.create(
            user=user_obj,
            title=f"Image {i}",
            url=f"https://example.com/img{i}.png",
            image=img_file,
        )
    images = list(Image.objects.all())
    for a, b in zip(images, images[1:]):
        assert a.created >= b.created


@pytest.mark.django_db
def test_image_users_like_add_and_remove(image, second_user):
    liker, _ = second_user
    image.users_like.add(liker)
    assert image.users_like.filter(pk=liker.pk).exists()
    image.users_like.remove(liker)
    assert not image.users_like.filter(pk=liker.pk).exists()


# ─── Form Tests ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/photo.jpg",
        "https://example.com/photo.jpeg",
        "https://example.com/photo.png",
        "https://example.com/photo.webp",
    ],
)
def test_clean_url_accepts_valid_extensions(url):
    form = ImageBookmarkForm(data={"title": "Test", "url": url, "description": ""})
    form.is_valid()
    assert "url" not in form.errors


def test_clean_url_rejects_invalid_extension():
    form = ImageBookmarkForm(
        data={
            "title": "Test",
            "url": "https://example.com/photo.gif",
            "description": "",
        }
    )
    form.is_valid()
    assert "url" in form.errors


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/photo.jpg",
        "ftps://example.com/photo.jpg",
    ],
)
def test_clean_url_rejects_schemes_the_worker_cannot_fetch(url):
    form = ImageBookmarkForm(data={"title": "Test", "url": url, "description": ""})
    form.is_valid()
    assert "url" in form.errors


# ─── View Tests: bookmarklet_launcher ────────────────────────────────────────


@pytest.mark.django_db
def test_bookmarklet_launcher_returns_javascript(client):
    response = client.get(reverse("images:bookmarklet_launcher"))
    assert response.status_code == 200
    assert "application/javascript" in response["Content-Type"]


# ─── View Tests: image_create ────────────────────────────────────────────────


@pytest.mark.django_db
def test_image_create_redirects_anonymous_user(client):
    response = client.get(reverse("images:create"))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_image_create_get_shows_form(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(
        reverse("images:create"), {"url": "https://example.com/photo.jpg"}
    )
    assert response.status_code == 200
    assert "form" in response.context


@pytest.mark.django_db
def test_image_create_post_valid_creates_image_and_redirects(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    mock_resp = MagicMock()
    mock_resp.content = MINIMAL_PNG
    mock_resp.raise_for_status = MagicMock()

    with patch("apps.images.tasks.requests.get", return_value=mock_resp):
        with patch("apps.images.tasks.get_thumbnail"):
            response = client.post(
                reverse("images:create"),
                {
                    "title": "My Image",
                    "url": "https://example.com/photo.jpg",
                    "description": "Nice photo",
                },
            )

    assert response.status_code == 302
    assert Image.objects.filter(title="My Image", user=user_obj).exists()


@pytest.mark.django_db
def test_image_create_dispatches_the_download_after_commit(
    client, user, django_capture_on_commit_callbacks
):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    with patch("apps.images.views.download_image.delay") as mock_delay:
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            client.post(
                reverse("images:create"),
                {
                    "title": "Deferred",
                    "url": "https://example.com/photo.jpg",
                    "description": "",
                },
            )
        mock_delay.assert_not_called()
        assert len(callbacks) == 1
        callbacks[0]()

    new_image = Image.objects.get(title="Deferred", user=user_obj)
    mock_delay.assert_called_once_with(new_image.id, new_image.url)


@pytest.mark.django_db
def test_image_create_post_invalid_shows_form_errors(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(
        reverse("images:create"),
        {
            "title": "Bad Image",
            "url": "https://example.com/photo.gif",  # invalid extension
            "description": "",
        },
    )

    assert response.status_code == 200
    assert response.context["form"].errors


# ─── View Tests: image_detail ────────────────────────────────────────────────


@pytest.mark.django_db
def test_image_detail_returns_200_with_image_context(client, image):
    response = client.get(reverse("images:detail", args=[image.id, image.slug]))
    assert response.status_code == 200
    assert response.context["image"] == image


@pytest.mark.django_db
def test_image_detail_renders_liked_false_when_not_liked(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:detail", args=[image.id, image.slug]))
    like_url = reverse("image-like", args=[image.id])
    assert f"likeButton('{like_url}', false, 0)".encode() in response.content


@pytest.mark.django_db
def test_image_detail_renders_liked_true_when_liked(client, user, image):
    user_obj, password = user
    image.users_like.add(user_obj)
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:detail", args=[image.id, image.slug]))
    like_url = reverse("image-like", args=[image.id])
    assert f"likeButton('{like_url}', true, 1)".encode() in response.content


@pytest.mark.django_db
def test_image_detail_hides_staff_from_liked_by(client, image, second_user, staff_user):
    liker, _ = second_user
    staff, _ = staff_user
    image.users_like.add(liker, staff)

    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    likers = list(response.context["users_like"])
    assert liker in likers
    assert staff not in likers


@pytest.mark.django_db
def test_image_detail_counts_the_likers_it_does_not_show(client, image, make_user):
    """A picture with a thousand likes used to hand every one of them to the
    template; past the limit the rest are a number."""
    extra = 3
    for index in range(LIKED_BY_LIMIT + extra):
        liker, _ = make_user(f"liker{index}", f"liker{index}@example.com", "pass12345")
        image.users_like.add(liker)

    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    assert len(response.context["users_like"]) == LIKED_BY_LIMIT
    assert response.context["hidden_likers"] == extra
    assert f"+{extra}".encode() in response.content


@pytest.mark.django_db
def test_image_detail_counts_nothing_extra_when_everyone_fits(
    client, image, second_user
):
    liker, _ = second_user
    image.users_like.add(liker)

    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    assert response.context["hidden_likers"] == 0


@pytest.mark.django_db
def test_image_detail_marks_nothing_liked_for_anonymous(client, image, second_user):
    """Whether the viewer liked it is now a question to the database, and there
    is nobody to ask it about."""
    liker, _ = second_user
    image.users_like.add(liker)

    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    assert response.context["liked_by_viewer"] is False


@pytest.mark.django_db
def test_image_detail_returns_404_for_unknown_id(client):
    response = client.get(reverse("images:detail", args=[9999, "no-such-slug"]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_image_detail_redirects_a_stale_slug_to_the_current_one(client, image):
    stale_url = reverse("images:detail", args=[image.id, "old-title"])

    response = client.get(stale_url)

    assert response.status_code == 302
    assert response["Location"] == image.get_absolute_url()


@pytest.mark.django_db
def test_image_detail_redirect_is_temporary(client, image):
    # A permanent redirect would be cached by the browser, so renaming an image
    # back to an earlier title would bounce readers between two addresses.
    response = client.get(reverse("images:detail", args=[image.id, "old-title"]))

    assert response.status_code == 302


@pytest.mark.django_db
def test_image_detail_does_not_count_a_view_when_redirecting(client, image):
    with patch("apps.images.views.record_image_view") as mock_record:
        client.get(reverse("images:detail", args=[image.id, "old-title"]))

    mock_record.assert_not_called()


@pytest.mark.django_db
def test_image_detail_does_not_count_view_when_image_empty(client, user):
    user_obj, _ = user
    pending = Image.objects.create(
        user=user_obj,
        title="Pending Image",
        url="https://example.com/pending.jpg",
    )
    with patch("apps.images.views.record_image_view") as mock_record:
        response = client.get(reverse("images:detail", args=[pending.id, pending.slug]))
    assert response.status_code == 200
    mock_record.assert_not_called()
    assert response.context["total_views"] == 0


@pytest.mark.django_db
def test_image_detail_counts_view_when_image_present(client, image):
    with patch("apps.images.views.record_image_view", return_value=1) as mock_record:
        response = client.get(reverse("images:detail", args=[image.id, image.slug]))
    assert response.status_code == 200
    mock_record.assert_called_once_with(image.id)


@pytest.mark.django_db
def test_image_detail_second_view_does_not_increment(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    url = reverse("images:detail", args=[image.id, image.slug])
    client.get(url)
    response = client.get(url)
    assert response.context["total_views"] == 1


@pytest.mark.django_db
def test_image_detail_different_users_count_separately(
    client, user, second_user, image
):
    user1, password1 = user
    user2, password2 = second_user
    url = reverse("images:detail", args=[image.id, image.slug])
    client.login(username=user1.username, password=password1)
    client.get(url)
    client.logout()
    client.login(username=user2.username, password=password2)
    response = client.get(url)
    assert response.context["total_views"] == 2


# ─── View Tests: image_upload ────────────────────────────────────────────────


@pytest.mark.django_db
def test_image_upload_redirects_anonymous_user(client):
    response = client.get(reverse("images:upload"))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_image_upload_get_shows_form(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:upload"))
    assert response.status_code == 200
    assert isinstance(response.context["form"], ImageUploadForm)


@pytest.mark.django_db
def test_image_upload_post_valid_creates_image_and_redirects(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    img_file = SimpleUploadedFile("photo.png", MINIMAL_PNG, content_type="image/png")
    with patch("apps.images.views.generate_image_thumbnails.delay"):
        response = client.post(
            reverse("images:upload"),
            {"title": "Uploaded Image", "description": "test", "image": img_file},
        )
    assert response.status_code == 302
    assert Image.objects.filter(title="Uploaded Image", user=user_obj).exists()


@pytest.mark.django_db
def test_image_upload_dispatches_thumbnail_generation(
    client, user, django_capture_on_commit_callbacks
):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    img_file = SimpleUploadedFile("photo.png", MINIMAL_PNG, content_type="image/png")
    with patch("apps.images.views.generate_image_thumbnails.delay") as mock_delay:
        with django_capture_on_commit_callbacks(execute=True):
            client.post(
                reverse("images:upload"),
                {"title": "Dispatched", "description": "", "image": img_file},
            )
    new_image = Image.objects.get(title="Dispatched", user=user_obj)
    mock_delay.assert_called_once_with(new_image.id)


@pytest.mark.django_db
def test_image_upload_post_invalid_extension_shows_errors(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    gif_file = SimpleUploadedFile("anim.gif", b"GIF89a", content_type="image/gif")
    response = client.post(
        reverse("images:upload"),
        {"title": "Bad Upload", "description": "", "image": gif_file},
    )
    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_image_upload_post_oversized_shows_errors(client, user, settings):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    settings.MAX_UPLOAD_SIZE = 1024 * 1024
    # A real image, so the size is what turns it away and not the content check
    big_file = SimpleUploadedFile(
        "big.png", png_bytes((600, 600), noise=True), content_type="image/png"
    )
    assert big_file.size > settings.MAX_UPLOAD_SIZE

    response = client.post(
        reverse("images:upload"),
        {"title": "Too Big", "description": "", "image": big_file},
    )

    assert response.status_code == 200
    assert "too large" in str(response.context["form"].errors["image"]).lower()
    assert not Image.objects.filter(title="Too Big").exists()


@pytest.mark.django_db
def test_image_detail_shows_owner_controls_to_the_author(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    assert reverse("images:edit", args=[image.id]).encode() in response.content
    assert reverse("images:delete", args=[image.id]).encode() in response.content


@pytest.mark.django_db
def test_image_detail_hides_owner_controls_from_others(client, second_user, image):
    other_user, password = second_user
    client.login(username=other_user.username, password=password)

    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    assert reverse("images:edit", args=[image.id]).encode() not in response.content
    assert reverse("images:delete", args=[image.id]).encode() not in response.content


@pytest.mark.django_db
def test_image_detail_hides_owner_controls_from_anonymous(client, image):
    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    assert reverse("images:edit", args=[image.id]).encode() not in response.content
    assert reverse("images:delete", args=[image.id]).encode() not in response.content


@pytest.mark.django_db
def test_image_detail_gives_anonymous_a_way_into_the_site(client, image):
    """This page is the one public page, so it is where a shared link lands
    someone with no account; without a navbar there was no way on from it."""
    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    assert b"<header" in response.content
    assert f"{reverse('login')}?register=1".encode() in response.content


@pytest.mark.django_db
def test_image_detail_invites_anonymous_from_the_right_sidebar(client, image):
    """The column has nothing to list for a guest, and left empty it reads as a
    page that failed to load."""
    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    assert b"Follow the people whose pictures you like" in response.content


@pytest.mark.django_db
def test_image_detail_carries_the_sign_in_dialog_for_anonymous(client, image):
    """The like and follow buttons stay in place for a guest, so pressing one
    has to answer with something; the server would only say 403."""
    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    assert b"auth-required.window" in response.content
    assert b"Alpine.store('signedIn', false)" in response.content


@pytest.mark.django_db
def test_image_detail_leaves_the_dialog_out_for_signed_in_people(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    assert b"auth-required.window" not in response.content
    assert b"Alpine.store('signedIn', true)" in response.content


@pytest.mark.django_db
def test_image_detail_keeps_the_sidebar_list_for_signed_in_people(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    assert b"Follow the people whose pictures you like" not in response.content


# ─── View Tests: image_edit ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_image_edit_redirects_anonymous_user(client, image):
    response = client.get(reverse("images:edit", args=[image.id]))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_image_edit_get_shows_form_with_current_values(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:edit", args=[image.id]))

    assert response.status_code == 200
    assert isinstance(response.context["form"], ImageEditForm)
    assert response.context["form"].initial["title"] == image.title


@pytest.mark.django_db
def test_image_edit_refuses_someone_elses_image(client, second_user, image):
    other_user, password = second_user
    client.login(username=other_user.username, password=password)

    response = client.get(reverse("images:edit", args=[image.id]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_image_edit_saves_title_and_description(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(
        reverse("images:edit", args=[image.id]),
        {"title": "Renamed Image", "description": "New words"},
    )

    image.refresh_from_db()
    assert response.status_code == 302
    assert image.title == "Renamed Image"
    assert image.description == "New words"


@pytest.mark.django_db
def test_image_edit_keeps_a_file_that_arrived_while_editing(user):
    user_obj, _ = user
    image = Image.objects.create(
        user=user_obj, title="Old Title", url="https://example.com/late.png"
    )

    form = ImageEditForm(
        {"title": "New Title", "description": "New words"},
        instance=Image.objects.get(id=image.id),
    )
    assert form.is_valid()
    # The download finishes between reading the row and saving the form
    Image.objects.filter(id=image.id).update(image="images/arrived.png")
    form.save()

    image.refresh_from_db()
    assert image.image.name == "images/arrived.png"
    assert image.title == "New Title"
    assert image.slug == "new-title"
    assert image.edited_at


@pytest.mark.django_db
def test_image_edit_redirects_to_the_new_address(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(
        reverse("images:edit", args=[image.id]),
        {"title": "Renamed Image", "description": ""},
    )

    image.refresh_from_db()
    assert response["Location"] == image.get_absolute_url()
    assert "renamed-image" in response["Location"]


@pytest.mark.django_db
def test_image_edit_shows_success_message(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(
        reverse("images:edit", args=[image.id]),
        {"title": "Renamed Image", "description": ""},
        follow=True,
    )

    assert [str(m) for m in response.context["messages"]] == ["Image updated"]


@pytest.mark.django_db
def test_image_edit_rejects_an_empty_title(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(
        reverse("images:edit", args=[image.id]),
        {"title": "", "description": "New words"},
    )

    image.refresh_from_db()
    assert response.status_code == 200
    assert response.context["form"].errors
    assert image.title == "Test Image"


@pytest.mark.django_db
def test_image_edit_stamps_the_edit_time(client, user, image):
    user_obj, password = user
    assert image.edited_at is None
    client.login(username=user_obj.username, password=password)

    client.post(
        reverse("images:edit", args=[image.id]),
        {"title": "Renamed Image", "description": ""},
    )

    image.refresh_from_db()
    assert image.edited_at is not None


@pytest.mark.django_db
def test_image_edit_without_changes_leaves_the_image_unmarked(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    client.post(
        reverse("images:edit", args=[image.id]),
        {"title": image.title, "description": image.description},
    )

    image.refresh_from_db()
    assert image.edited_at is None


@pytest.mark.django_db
def test_image_detail_marks_an_edited_image(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    detail_url = reverse("images:detail", args=[image.id, image.slug])

    assert b"edited" not in client.get(detail_url).content

    client.post(
        reverse("images:edit", args=[image.id]),
        {"title": "Test Image", "description": "New words"},
    )

    assert b"edited" in client.get(detail_url).content


@pytest.mark.django_db
def test_image_edit_ignores_a_posted_file(client, user, image):
    user_obj, password = user
    original_file = image.image.name
    client.login(username=user_obj.username, password=password)
    replacement = SimpleUploadedFile("other.png", MINIMAL_PNG, content_type="image/png")

    client.post(
        reverse("images:edit", args=[image.id]),
        {"title": "Renamed Image", "description": "", "image": replacement},
    )

    image.refresh_from_db()
    assert image.image.name == original_file


# ─── View Tests: image_delete ────────────────────────────────────────────────


@pytest.mark.django_db
def test_image_delete_redirects_anonymous_user(client, image):
    response = client.post(reverse("images:delete", args=[image.id]))
    assert response.status_code == 302
    assert "login" in response["Location"]
    assert Image.objects.filter(id=image.id).exists()


@pytest.mark.django_db
def test_image_delete_rejects_get(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:delete", args=[image.id]))

    assert response.status_code == 405
    assert Image.objects.filter(id=image.id).exists()


@pytest.mark.django_db
def test_image_delete_removes_own_image_and_redirects(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(reverse("images:delete", args=[image.id]))

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('images:list')}?mine=1"
    assert not Image.objects.filter(id=image.id).exists()


@pytest.mark.django_db
def test_image_delete_returns_to_the_page_it_started_from(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(
        reverse("images:delete", args=[image.id]), {"next": reverse("my_profile")}
    )

    assert response["Location"] == reverse("my_profile")


@pytest.mark.django_db
def test_image_delete_does_not_return_to_the_deleted_image(client, user, image):
    """Deleting from the image's own page has nowhere to go back to."""
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(
        reverse("images:delete", args=[image.id]),
        {"next": image.get_absolute_url()},
    )

    assert response["Location"] == f"{reverse('images:list')}?mine=1"


@pytest.mark.django_db
def test_image_delete_ignores_a_next_pointing_off_the_site(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(
        reverse("images:delete", args=[image.id]), {"next": "https://evil.example.com/"}
    )

    assert response["Location"] == f"{reverse('images:list')}?mine=1"


@pytest.mark.django_db
def test_image_delete_shows_success_message(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(reverse("images:delete", args=[image.id]), follow=True)

    assert [str(m) for m in response.context["messages"]] == ["Image deleted"]


@pytest.mark.django_db
def test_image_delete_refuses_someone_elses_image(client, second_user, image):
    other_user, password = second_user
    client.login(username=other_user.username, password=password)

    response = client.post(reverse("images:delete", args=[image.id]))

    assert response.status_code == 404
    assert Image.objects.filter(id=image.id).exists()


@pytest.mark.django_db
def test_image_delete_returns_404_for_unknown_id(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.post(reverse("images:delete", args=[9999]))

    assert response.status_code == 404


# ─── View Tests: image_status ────────────────────────────────────────────────


@pytest.mark.django_db
def test_image_status_returns_200(client, image):
    response = client.get(reverse("images:status", args=[image.id]))
    assert response.status_code == 200


@pytest.mark.django_db
def test_image_status_ready_renders_img_without_polling(client, image):
    response = client.get(reverse("images:status", args=[image.id]))
    assert b"<img" in response.content
    assert b"hx-trigger" not in response.content


@pytest.mark.django_db
def test_image_status_pending_renders_skeleton_with_polling(client, user):
    user_obj, _ = user
    pending = Image.objects.create(
        user=user_obj,
        title="Pending Image",
        url="https://example.com/pending.jpg",
    )
    response = client.get(reverse("images:status", args=[pending.id]))
    assert b"hx-trigger" in response.content
    assert b"<img" not in response.content


@pytest.mark.django_db
def test_image_status_failed_shows_the_reason_and_stops_polling(client, user):
    user_obj, _ = user
    failed = Image.objects.create(
        user=user_obj,
        title="Failed Image",
        url="https://example.com/failed.jpg",
        download_error="The link did not answer with an image.",
    )

    response = client.get(reverse("images:status", args=[failed.id]))

    assert b"The link did not answer with an image." in response.content
    assert b"hx-trigger" not in response.content


@pytest.mark.django_db
def test_image_status_counts_the_attempts_it_asks_for(client, user):
    user_obj, _ = user
    pending = Image.objects.create(
        user=user_obj, title="Pending Image", url="https://example.com/pending.jpg"
    )
    url = reverse("images:status", args=[pending.id])

    assert b"attempt=1" in client.get(url).content
    assert b"attempt=8" in client.get(url, {"attempt": "7"}).content
    # A hand-written value cannot break the count
    assert b"attempt=1" in client.get(url, {"attempt": "soon"}).content


@pytest.mark.django_db
def test_image_status_slows_down_and_then_gives_up_on_asking(client, user):
    user_obj, _ = user
    pending = Image.objects.create(
        user=user_obj, title="Pending Image", url="https://example.com/pending.jpg"
    )
    url = reverse("images:status", args=[pending.id])

    assert b"every 2s" in client.get(url, {"attempt": STATUS_POLL_SLOWDOWN - 1}).content
    assert b"every 5s" in client.get(url, {"attempt": STATUS_POLL_SLOWDOWN}).content

    last = client.get(url, {"attempt": STATUS_POLL_LIMIT})
    assert b"hx-trigger" not in last.content
    assert b"Reload the page" in last.content


# ─── View Tests: image_retry_download ────────────────────────────────────────


@pytest.fixture
def failed_image(user):
    user_obj, _ = user
    return Image.objects.create(
        user=user_obj,
        title="Failed Image",
        url="https://example.com/failed.png",
        download_error="The link did not answer with an image.",
    )


@pytest.mark.django_db
def test_image_retry_redirects_anonymous_user(client, failed_image):
    response = client.post(reverse("images:retry", args=[failed_image.id]))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_image_retry_rejects_a_get(client, user, failed_image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:retry", args=[failed_image.id]))

    assert response.status_code == 405


@pytest.mark.django_db
def test_image_retry_is_404_for_someone_else(client, second_user, failed_image):
    other, password = second_user
    client.login(username=other.username, password=password)

    response = client.post(reverse("images:retry", args=[failed_image.id]))

    assert response.status_code == 404
    failed_image.refresh_from_db()
    assert failed_image.download_error


@pytest.mark.django_db
def test_image_retry_clears_the_reason_and_asks_again(
    client, user, failed_image, django_capture_on_commit_callbacks
):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    with patch("apps.images.views.download_image.delay") as mock_delay:
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(reverse("images:retry", args=[failed_image.id]))

    failed_image.refresh_from_db()
    assert response.status_code == 302
    assert failed_image.download_error == ""
    mock_delay.assert_called_once_with(failed_image.id, failed_image.url)


@pytest.mark.django_db
def test_image_status_offers_the_retry_to_the_author_only(
    client, user, second_user, failed_image
):
    status_url = reverse("images:status", args=[failed_image.id])
    retry_url = reverse("images:retry", args=[failed_image.id]).encode()

    assert retry_url not in client.get(status_url).content

    other, password = second_user
    client.login(username=other.username, password=password)
    assert retry_url not in client.get(status_url).content
    client.logout()

    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    assert retry_url in client.get(status_url).content


@pytest.mark.django_db
def test_image_retry_leaves_a_downloaded_image_alone(
    client, user, image, django_capture_on_commit_callbacks
):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    with patch("apps.images.views.download_image.delay") as mock_delay:
        with django_capture_on_commit_callbacks(execute=True):
            client.post(reverse("images:retry", args=[image.id]))

    mock_delay.assert_not_called()


# ─── View Tests: image_list ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_image_list_redirects_anonymous_user(client):
    response = client.get(reverse("images:list"))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_image_list_returns_200(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:list"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_image_list_uses_full_template(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:list"))
    template_names = [t.name for t in response.templates]
    assert "images/list.html" in template_names


@pytest.mark.django_db
def test_image_list_images_only_uses_partial_template(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:list"), {"images_only": "1"})
    assert response.status_code == 200
    template_names = [t.name for t in response.templates]
    assert "images/partials/image_cards.html" in template_names
    assert "images/list.html" not in template_names


def _make_images(owner, count):
    for number in range(count):
        Image.objects.create(
            user=owner,
            title=f"Image {number}",
            url=f"https://example.com/img{number}.png",
            image=SimpleUploadedFile(
                f"img{number}.png", MINIMAL_PNG, content_type="image/png"
            ),
        )


@pytest.mark.django_db
def test_image_list_scroll_past_the_last_image_returns_empty_body(client, user):
    """What was left to load can be gone by the time the scroll asks for it."""
    user_obj, password = user
    _make_images(user_obj, 7)
    client.login(username=user_obj.username, password=password)

    first = client.get(reverse("images:list"))
    Image.objects.exclude(
        id__in=[image.id for image in first.context["images"]]
    ).delete()
    response = client.get(
        reverse("images:list"),
        {"images_only": "1", "after": first.context["next_cursor"]},
    )

    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.django_db
def test_image_list_next_batch_contains_the_remaining_images(client, user):
    user_obj, password = user
    _make_images(user_obj, 10)
    client.login(username=user_obj.username, password=password)

    first = client.get(reverse("images:list"))
    second = client.get(reverse("images:list"), {"after": first.context["next_cursor"]})

    assert len(first.context["images"]) == 6
    assert len(second.context["images"]) == 4
    assert second.context["next_cursor"] == ""


@pytest.mark.django_db
def test_image_list_repeats_nothing_when_someone_uploads_mid_scroll(client, user):
    """Page numbers repeated the first batch here: a fresh upload pushed every
    image one place down."""
    user_obj, password = user
    _make_images(user_obj, 10)
    client.login(username=user_obj.username, password=password)

    first = client.get(reverse("images:list"))
    _make_images(user_obj, 3)
    second = client.get(
        reverse("images:list"),
        {"images_only": "1", "after": first.context["next_cursor"]},
    )

    seen = {image.id for image in first.context["images"]}
    following = {image.id for image in second.context["images"]}
    assert not seen & following


@pytest.mark.django_db
@pytest.mark.parametrize("query", [{}, {"mine": "1"}])
def test_image_list_never_prints_a_template_comment(client, user, image, query):
    # Django only strips single-line {# #}; a multi-line one reaches the reader
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:list"), query)

    assert b"{#" not in response.content


@pytest.mark.django_db
def test_image_detail_never_prints_a_template_comment(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    assert b"{#" not in response.content


@pytest.mark.django_db
def test_image_list_shows_owner_controls_on_my_images(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:list"), {"mine": "1"})

    assert reverse("images:edit", args=[image.id]).encode() in response.content
    assert reverse("images:delete", args=[image.id]).encode() in response.content


@pytest.mark.django_db
def test_image_list_hides_owner_controls_on_the_common_list(client, user, image):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:list"))

    assert reverse("images:edit", args=[image.id]).encode() not in response.content
    assert reverse("images:delete", args=[image.id]).encode() not in response.content


# ─── View Tests: HTMX infinite scroll sentinel ───────────────────────────────


@pytest.mark.django_db
def test_image_list_partial_carries_a_sentinel_while_more_is_left(client, user):
    user_obj, password = user
    _make_images(user_obj, 9)
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:list"), {"images_only": "1"})

    assert response.status_code == 200
    cursor = response.context["next_cursor"]
    assert f'hx-get="?images_only=1&amp;after={cursor}"'.encode() in response.content


@pytest.mark.django_db
def test_image_list_partial_drops_the_sentinel_on_the_last_batch(client, user):
    user_obj, password = user
    _make_images(user_obj, 9)
    client.login(username=user_obj.username, password=password)

    first = client.get(reverse("images:list"), {"images_only": "1"})
    last = client.get(
        reverse("images:list"),
        {"images_only": "1", "after": first.context["next_cursor"]},
    )

    assert last.status_code == 200
    assert b"hx-get" not in last.content


# ─── View Tests: image_ranking ───────────────────────────────────────────────


def make_ranked_images(user_obj, scores):
    """Create images with fixed view/like counts: scores is (views, likes) per image."""
    images = []
    for i, (views, likes) in enumerate(scores):
        image = Image.objects.create(
            user=user_obj,
            title=f"Ranked {i}",
            url=f"https://example.com/ranked{i}.png",
        )
        Image.objects.filter(id=image.id).update(total_views=views, total_likes=likes)
        image.refresh_from_db()
        images.append(image)
    return images


@pytest.mark.django_db
def test_image_ranking_redirects_anonymous_user(client):
    response = client.get(reverse("images:ranking"))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_image_ranking_returns_200(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    response = client.get(reverse("images:ranking"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_image_ranking_orders_podium_by_views(client, user):
    user_obj, password = user
    low, high, mid = make_ranked_images(user_obj, [(1, 90), (30, 0), (10, 50)])
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:ranking"))

    assert list(response.context["top3"]) == [high, mid, low]


@pytest.mark.django_db
def test_image_ranking_orders_podium_by_likes_when_asked(client, user):
    user_obj, password = user
    most_liked, middle, most_viewed = make_ranked_images(
        user_obj, [(1, 90), (10, 50), (30, 0)]
    )
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:ranking"), {"sort": "likes"})

    assert response.context["sort"] == "likes"
    assert list(response.context["top3"]) == [most_liked, middle, most_viewed]


@pytest.mark.django_db
def test_image_ranking_falls_back_to_views_for_unknown_sort(client, user):
    user_obj, password = user
    most_liked, middle, most_viewed = make_ranked_images(
        user_obj, [(1, 90), (10, 50), (30, 0)]
    )
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:ranking"), {"sort": "bogus"})

    assert response.context["sort"] == "views"
    assert list(response.context["top3"]) == [most_viewed, middle, most_liked]


@pytest.mark.django_db
def test_image_ranking_shows_live_view_counts(client, user):
    user_obj, password = user
    top, _, _ = make_ranked_images(user_obj, [(100, 0), (10, 0), (1, 0)])
    record_image_view(top.id)
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:ranking"))

    assert response.context["top3"][0].total_views == 101


@pytest.mark.django_db
def test_image_ranking_list_starts_below_the_podium(client, user):
    user_obj, password = user
    images = make_ranked_images(user_obj, [(score, 0) for score in range(5, 0, -1)])
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:ranking"))

    ranking_list = response.context["ranking_list"]
    assert list(ranking_list) == images[3:]
    assert [img.rank for img in ranking_list] == [4, 5]


@pytest.mark.django_db
def test_image_ranking_second_page_continues_numbering(client, user):
    user_obj, password = user
    make_ranked_images(user_obj, [(score, 0) for score in range(20, 0, -1)])
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:ranking"), {"page": "2"})

    # 20 images: 3 on the podium, 10 on the first page, the rest here.
    ranks = [img.rank for img in response.context["ranking_list"]]
    assert ranks == [14, 15, 16, 17, 18, 19, 20]
    assert response.context["has_next"] is False


@pytest.mark.django_db
def test_image_ranking_only_uses_partial_template(client, user):
    user_obj, password = user
    make_ranked_images(user_obj, [(5, 0), (4, 0), (3, 0), (2, 0)])
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:ranking"), {"ranking_only": "1"})

    template_names = [t.name for t in response.templates]
    assert "images/partials/ranking_rows.html" in template_names
    assert "images/ranking.html" not in template_names


@pytest.mark.django_db
def test_image_ranking_empty_page_with_ranking_only_returns_empty_body(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(
        reverse("images:ranking"), {"page": "999", "ranking_only": "1"}
    )

    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.django_db
def test_image_ranking_without_images_shows_no_podium(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:ranking"))

    assert response.status_code == 200
    assert response.context["top3"] == []
    assert b"No images to rank yet" in response.content


@pytest.mark.django_db
@pytest.mark.parametrize("count", [1, 2])
def test_image_ranking_lists_rows_until_the_podium_can_be_filled(client, user, count):
    user_obj, password = user
    images = make_ranked_images(user_obj, [(10 - i, 0) for i in range(count)])
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:ranking"))

    # A partly filled podium would leave tiles off-centre and linking nowhere,
    # so everything is shown as numbered rows instead. Counting the applied
    # animation, not its name — the keyframes are always declared.
    assert response.context["top3"] == []
    assert list(response.context["ranking_list"]) == images
    assert [img.rank for img in response.context["ranking_list"]] == list(
        range(1, count + 1)
    )
    assert response.content.count(b"animation: glow-") == 0


@pytest.mark.django_db
def test_image_ranking_fills_the_podium_from_three_images(client, user):
    user_obj, password = user
    images = make_ranked_images(user_obj, [(30, 0), (20, 0), (10, 0)])
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:ranking"))

    assert list(response.context["top3"]) == images
    assert list(response.context["ranking_list"]) == []
    assert response.content.count(b"animation: glow-") == 3


@pytest.mark.django_db
@pytest.mark.parametrize("page", ["-5", "0", "abc"])
def test_image_ranking_survives_a_bad_page_number(client, user, image, page):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:ranking"), {"page": page})

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("page", ["-5", "0", "abc"])
def test_image_list_survives_a_bad_page_number(client, user, image, page):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:list"), {"page": page})

    assert response.status_code == 200


@pytest.mark.django_db
def test_image_list_without_images_shows_an_invitation(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:list"))

    assert b"No images here yet" in response.content


@pytest.mark.django_db
def test_image_ranking_sentinel_keeps_the_current_sort(client, user):
    user_obj, password = user
    make_ranked_images(user_obj, [(score, 0) for score in range(20, 0, -1)])
    client.login(username=user_obj.username, password=password)

    response = client.get(
        reverse("images:ranking"), {"ranking_only": "1", "sort": "likes"}
    )

    assert b"page=2&amp;sort=likes" in response.content


# ─── View Tests: pages survive a Redis outage ────────────────────────────────


@pytest.mark.django_db
def test_image_detail_serves_stored_views_when_redis_is_down(
    client, broken_redis, image
):
    Image.objects.filter(id=image.id).update(total_views=42)

    response = client.get(reverse("images:detail", args=[image.id, image.slug]))

    assert response.status_code == 200
    assert response.context["total_views"] == 42


@pytest.mark.django_db
def test_image_list_renders_when_redis_is_down(client, broken_redis, user, image):
    user_obj, password = user
    Image.objects.filter(id=image.id).update(total_views=42)
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:list"))

    assert response.status_code == 200
    assert [img.total_views for img in response.context["images"]] == [42]


@pytest.mark.django_db
def test_image_ranking_renders_when_redis_is_down(client, broken_redis, user):
    user_obj, password = user
    images = make_ranked_images(user_obj, [(30, 0), (10, 0), (1, 0)])
    client.login(username=user_obj.username, password=password)

    response = client.get(reverse("images:ranking"))

    assert response.status_code == 200
    assert list(response.context["top3"]) == images
