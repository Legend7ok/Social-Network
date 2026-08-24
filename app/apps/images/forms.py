from django import forms
from django.core.validators import URLValidator
from django.utils import timezone
from urllib.parse import urlparse
import os

from core.validators import VALID_IMAGE_EXTENSIONS, validate_image_upload
from .models import Image


class ImageBookmarkForm(forms.ModelForm):
    # Django accepts ftp and ftps addresses as well, and the worker that picks
    # the bookmark up speaks neither.
    url = forms.URLField(
        max_length=2000,
        widget=forms.HiddenInput,
        validators=[URLValidator(schemes=["http", "https"])],
    )

    class Meta:
        model = Image
        fields = ["title", "url", "description"]

    def clean_url(self):
        url = self.cleaned_data["url"]
        path = urlparse(url).path
        extension = os.path.splitext(path)[1].lstrip(".").lower()

        if not extension:
            raise forms.ValidationError("The link must end with a file extension.")

        if extension not in VALID_IMAGE_EXTENSIONS:
            raise forms.ValidationError(
                "The link must end with one of: %(exts)s.",
                params={"exts": ", ".join(VALID_IMAGE_EXTENSIONS)},
            )

        return url


class ImageEditForm(forms.ModelForm):
    # The file itself stays put: views, likes, thumbnails and the ranking are
    # all tied to it, so swapping it would silently rewrite an image's history.
    class Meta:
        model = Image
        fields = ["title", "description"]

    def save(self, commit=True):
        if self.has_changed():
            self.instance.edited_at = timezone.now()
        return super().save(commit=commit)


class ImageUploadForm(forms.ModelForm):
    class Meta:
        model = Image
        fields = ["title", "description", "image"]

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            raise forms.ValidationError("Please select an image file.")
        validate_image_upload(image)
        return image
