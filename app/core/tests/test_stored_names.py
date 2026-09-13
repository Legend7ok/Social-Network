"""What keeps a replaced picture from being served in place of its successor.

Stored names are never reused: the storage adds a suffix when the name it was
given is taken. Thumbnails are remembered by that name, so a reused one would
have the site handing out the previous picture's cut-down copies under the new
picture - and nothing would ever correct it, because as far as the cache is
concerned the name it knows is still there.
"""

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from conftest import MINIMAL_PNG, png_bytes
from settings.storages import build_storages


def upload(profile, callbacks, content):
    with callbacks(execute=False):
        profile.photo = SimpleUploadedFile(
            "photo1.png", content, content_type="image/png"
        )
        profile.save()
    return profile.photo.name


@pytest.mark.django_db
def test_the_same_file_name_twice_is_stored_twice(
    user, django_capture_on_commit_callbacks
):
    """A person renames a picture on their own machine and uploads it under the
    name the previous one had - a different picture, the same file name."""
    profile = user[0].profile

    first = upload(profile, django_capture_on_commit_callbacks, MINIMAL_PNG)
    second = upload(
        profile, django_capture_on_commit_callbacks, png_bytes((2, 2), noise=True)
    )

    assert first != second
    assert default_storage.exists(first)
    assert default_storage.exists(second)


@pytest.mark.django_db
def test_the_replaced_file_is_handed_over_by_its_own_name(
    user, django_capture_on_commit_callbacks, monkeypatch
):
    """The name that goes to the worker is the one that was stored, not the one
    the browser sent - otherwise the deletion would take the new picture."""
    dropped = []
    monkeypatch.setattr(
        "apps.account.signals.delete_avatar_file.delay",
        lambda name: dropped.append(name),
    )
    profile = user[0].profile

    first = upload(profile, django_capture_on_commit_callbacks, MINIMAL_PNG)
    with django_capture_on_commit_callbacks(execute=True):
        profile.photo = SimpleUploadedFile(
            "photo1.png", png_bytes((2, 2), noise=True), content_type="image/png"
        )
        profile.save()

    assert dropped == [first]
    assert profile.photo.name != first


def test_production_never_overwrites_a_stored_file():
    """The guarantee above is a setting, and this is the one place it is
    written down. Turning it on to save room in the bucket would give two
    different pictures one name, and the thumbnails of the first would be
    served for the second.
    """
    storages = build_storages(required=False)

    assert storages["default"]["OPTIONS"]["file_overwrite"] is False
