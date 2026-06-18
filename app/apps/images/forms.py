from django import forms
from urllib.parse import urlparse
import os

from core.validators import VALID_IMAGE_EXTENSIONS, validate_image_upload
from .models import Image


class ImageBookmarkForm(forms.ModelForm):
    class Meta:
        model = Image
        fields = ["title", "url", "description"]
        widgets = {
            "url": forms.HiddenInput,
        }

    def clean_url(self):
        url = self.cleaned_data["url"]
        path = urlparse(url).path
        extension = os.path.splitext(path)[1].lstrip(".").lower()

        if not extension:
            raise forms.ValidationError("URL must have a file extension")

        if extension not in VALID_IMAGE_EXTENSIONS:
            raise forms.ValidationError(
                "URL must end with one of {}".format(VALID_IMAGE_EXTENSIONS)
            )

        return url


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
