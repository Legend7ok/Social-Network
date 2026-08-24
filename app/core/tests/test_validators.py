import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from conftest import MINIMAL_PNG
from core.validators import validate_image_content, validate_image_upload


def make_image_bytes(fmt, size=(2, 2)):
    buffer = io.BytesIO()
    Image.new("RGB", size).save(buffer, format=fmt)
    return buffer.getvalue()


def test_validate_image_content_returns_the_recognised_format():
    assert validate_image_content(io.BytesIO(MINIMAL_PNG)) == "PNG"


def test_validate_image_content_rejects_bytes_that_are_not_an_image():
    with pytest.raises(ValidationError):
        validate_image_content(io.BytesIO(b"not an image at all"))


def test_validate_image_content_rejects_a_format_outside_the_list():
    with pytest.raises(ValidationError):
        validate_image_content(io.BytesIO(make_image_bytes("GIF")))


def test_validate_image_content_rejects_an_image_beyond_the_pixel_limit(settings):
    settings.MAX_IMAGE_PIXELS = 3
    with pytest.raises(ValidationError):
        validate_image_content(io.BytesIO(make_image_bytes("PNG")))


def test_validate_image_content_leaves_the_file_at_the_start():
    file = io.BytesIO(MINIMAL_PNG)
    validate_image_content(file)
    assert file.read() == MINIMAL_PNG


def test_validate_image_upload_accepts_a_real_image():
    file = SimpleUploadedFile("photo.png", MINIMAL_PNG, content_type="image/png")
    validate_image_upload(file)


def test_validate_image_upload_rejects_a_renamed_file():
    file = SimpleUploadedFile(
        "photo.png", b"#!/bin/sh\necho hi\n", content_type="image/png"
    )
    with pytest.raises(ValidationError):
        validate_image_upload(file)
