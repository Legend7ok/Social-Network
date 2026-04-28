from django import forms
from urllib.parse import urlparse
import os

from .models import Image


class ImageCreateForm(forms.ModelForm):
    class Meta:
        model = Image
        fields = ["title", "url", "description"]
        widgets = {
            "url": forms.HiddenInput,
        }

    def clean_url(self):
        url = self.cleaned_data["url"]
        valid_extensions = ["jpg", "jpeg", "png", "webp"]
        path = urlparse(url).path
        extension = os.path.splitext(path)[1].lstrip(".").lower()

        if not extension:
            raise forms.ValidationError("URL must have a file extension")

        if extension not in valid_extensions:
            raise forms.ValidationError(
                "URL must end with one of {}".format(valid_extensions)
            )

        return url

