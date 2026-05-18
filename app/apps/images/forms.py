from django import forms
from urllib.parse import urlparse
import os

from .models import Image

VALID_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]


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

        if extension not in VALID_EXTENSIONS:
            raise forms.ValidationError(
                "URL must end with one of {}".format(VALID_EXTENSIONS)
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
        ext = os.path.splitext(image.name)[1].lstrip(".").lower()
        if ext not in VALID_EXTENSIONS:
            raise forms.ValidationError(
                "File must be one of {}".format(VALID_EXTENSIONS)
            )
        return image
