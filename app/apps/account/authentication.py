from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models.functions import Lower

User = get_user_model()


class EmailAuthBackend(ModelBackend):
    """Signing in with an email address instead of a username.

    Subclasses ModelBackend so permissions, the inactive-user rule and session
    lookups keep Django's own behaviour; only finding the user differs.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # An empty address would match every account social auth left blank.
        if not username or not password:
            return None

        try:
            user = User.objects.annotate(email_lower=Lower("email")).get(
                email_lower=username.lower()
            )
        except User.DoesNotExist:
            # Keep hashing so an unknown address takes as long as a wrong password.
            User().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
