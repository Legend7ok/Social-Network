from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import UsernameField
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from core.validators import validate_image_upload
from .models import Profile


class UserRegistrationForm(forms.ModelForm):
    """One password field, revealed by the eye toggle in the template; the form
    owns hashing so no caller can store a raw password by mistake."""

    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
    )
    email = forms.EmailField(label="Email", required=True)

    class Meta:
        model = User
        fields = ("username", "email")
        field_classes = {"username": UsernameField}

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already in use")
        return email

    def _post_clean(self):
        # Runs after the instance is populated, so validators that compare the
        # password against the username and email have something to compare to.
        super()._post_clean()
        password = self.cleaned_data.get("password")
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except ValidationError as error:
                self.add_error("password", error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def clean_email(self):
        email = self.cleaned_data["email"]
        qs = User.objects.exclude(id=self.instance.id).filter(email=email)

        if qs.exists():
            raise forms.ValidationError("Email already in use")
        return email


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["date_of_birth", "photo"]

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo:
            validate_image_upload(photo)
        return photo


class ProfilePhotoForm(ProfileEditForm):
    """Photo-only submit (navbar/profile dropdown); inherits clean_photo."""

    class Meta(ProfileEditForm.Meta):
        fields = ["photo"]
