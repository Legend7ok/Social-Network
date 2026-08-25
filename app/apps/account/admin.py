from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Profile


class ProfileInline(admin.StackedInline):
    """The profile is part of an account, not a row of its own: the feed and the
    profile page read request.user.profile directly and answer with a 500 once
    it is gone, while the signal only guarantees it at sign-up. Editing it here
    leaves no way to delete it alone; deleting the user still takes it along."""

    model = Profile
    can_delete = False
    verbose_name_plural = "profile"


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
