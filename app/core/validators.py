import os

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image

VALID_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
# The extension to store a file under once Pillow says what it really is.
IMAGE_FORMAT_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
VALID_IMAGE_FORMATS = set(IMAGE_FORMAT_EXTENSIONS)
# image/jpg is not a registered type, but enough servers send it anyway.
VALID_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def validate_image_content(file):
    """Check that the bytes really are an image we accept and return the format
    Pillow recognised. Only the header is read — verify() decodes nothing."""
    try:
        image = Image.open(file)
        image.verify()
    # Pillow raises anything from OSError to struct errors on hostile input,
    # and the caller cannot act on the difference.
    except Exception as exc:
        raise ValidationError("File must be a valid image.") from exc
    finally:
        file.seek(0)

    if image.format not in VALID_IMAGE_FORMATS:
        raise ValidationError(
            "File must be one of %(exts)s.",
            params={"exts": ", ".join(VALID_IMAGE_EXTENSIONS)},
        )

    width, height = image.size
    if width * height > settings.MAX_IMAGE_PIXELS:
        raise ValidationError(
            "Image is too large. Max size is %(mp)s megapixels.",
            params={"mp": settings.MAX_IMAGE_PIXELS // 1_000_000},
        )

    return image.format


def validate_image_upload(file):
    """Single source of truth for uploaded image files: name, weight, content."""
    ext = os.path.splitext(file.name)[1].lstrip(".").lower()
    if ext not in VALID_IMAGE_EXTENSIONS:
        raise ValidationError(
            "File must be one of %(exts)s.",
            params={"exts": ", ".join(VALID_IMAGE_EXTENSIONS)},
        )
    if file.size > settings.MAX_UPLOAD_SIZE:
        raise ValidationError(
            "File too large. Max size is %(mb)s MB.",
            params={"mb": settings.MAX_UPLOAD_SIZE // (1024 * 1024)},
        )
    validate_image_content(file)
