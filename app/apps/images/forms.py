from django import forms
from .models import Image
from django.core.files.base import ContentFile
from django.utils.text import slugify
from urllib.parse import urlparse
import os
import requests

class ImageCreateForm(forms.ModelForm):
    class Meta:
        model = Image
        fields = ['title', 'url', 'description']
        widgets = {
            'url': forms.HiddenInput,
        }

    def clean_url(self):
        url = self.cleaned_data['url']
        valid_extensions = ['jpg', 'jpeg', 'png', 'webp']
        path = urlparse(url).path
        extension = os.path.splitext(path)[1].lstrip('.').lower()

        if not extension:
            raise forms.ValidationError('URL must have a file extension')

        if extension not in valid_extensions:
            raise forms.ValidationError(
                'URL must end with one of {}'.format(valid_extensions)
            )

        return url


    def save(self, force_insert=False, force_update=False, commit=True):
        image = super().save(commit=False)
        image_url = self.cleaned_data['url']
        name = slugify(image.title)
        extension = os.path.splitext(urlparse(image_url).path)[1].lstrip('.').lower()
        image_name = f'{name}.{extension}'

        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            raise forms.ValidationError('Could not download image from the given URL.')

        image.image.save(image_name, ContentFile(response.content), save=False)

        if commit:
            image.save()

        return image
