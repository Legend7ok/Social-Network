import os

from django.conf import settings
from django.core.exceptions import ValidationError

VALID_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]


def validate_image_upload(file):
    """Single source of truth for uploaded image files: extension + size."""
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
