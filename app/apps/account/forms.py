from django import forms
from django.contrib.auth.models import User
from .models import Profile


class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        max_length=100, label="Password", widget=forms.PasswordInput
    )
    password2 = forms.CharField(
        max_length=100, label="Repeat password", widget=forms.PasswordInput
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "email")

    def clean_password2(self):
        cd = self.cleaned_data
        if cd["password"] != cd["password2"]:
            raise forms.ValidationError("Passwords don't match")
        return cd["password2"]

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already in use")
        return email


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
