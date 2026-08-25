from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, UsernameField
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from core.validators import validate_image_upload
from .models import Profile, users_with_email, users_with_username

EMAIL_MAX_LENGTH = User._meta.get_field("email").max_length


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    """Sign-in takes an email address as well as a username."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The parent sizes this field after the username column, which stops at
        # 150 characters and would turn away a longer address.
        field = self.fields["username"]
        field.max_length = EMAIL_MAX_LENGTH
        field.widget.attrs["maxlength"] = EMAIL_MAX_LENGTH
        field.label = "Email or username"


class UserRegistrationForm(forms.ModelForm):
    """One password field, revealed by the eye toggle in the template; the form
    owns hashing so no caller can store a raw password by mistake."""

    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
    )
    # Declared here because the model leaves email optional, while an account
    # without one has no way back in: no email sign-in, no password reset.
    email = forms.EmailField(label="Email", required=True, max_length=EMAIL_MAX_LENGTH)

    class Meta:
        model = User
        fields = ("username", "email")
        field_classes = {"username": UsernameField}

    def clean_username(self):
        username = self.cleaned_data["username"]
        if users_with_username(username).exists():
            raise forms.ValidationError("This username is already taken")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if users_with_email(email).exists():
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
    # Same reason as on registration: clearing the address would lock the owner
    # out of their own account. Changing it stays allowed.
    email = forms.EmailField(label="Email", required=True, max_length=EMAIL_MAX_LENGTH)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if users_with_email(email).exclude(pk=self.instance.pk).exists():
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
