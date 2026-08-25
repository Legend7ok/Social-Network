from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from .models import users_with_email, users_with_username

User = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    """Signing in with an email address, or with a username typed in any casing.

    Subclasses ModelBackend so permissions, the inactive-user rule and session
    lookups keep Django's own behaviour; only finding the user differs.

    Matching a username loosely is only safe because the database holds names
    unique regardless of case (account/0008): without that index, bob and Bob
    could be two people and this would sign one of them into the other's
    account.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # An empty address would match every account social auth left blank.
        if not username or not password:
            return None

        # Both lookups go through the case-insensitive indexes. Django's own
        # backend runs first and settles exact matches, so this one mostly
        # handles addresses and unusual casing.
        user = (
            users_with_email(username.lower()).first()
            or users_with_username(username).first()
        )
        if user is None:
            # Keep hashing so an unknown name takes as long as a wrong password.
            User().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
