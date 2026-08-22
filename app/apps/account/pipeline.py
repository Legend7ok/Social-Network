from social_core.exceptions import AuthException

from .models import users_with_email


def refuse_a_taken_address(backend, details, user=None, *args, **kwargs):
    """Stop a social login whose address already belongs to somebody.

    The step before this one only joins ACTIVE accounts, so a disabled account
    leaves its address taken while looking free to the pipeline. Creating the
    user would then hit the unique email index, and a database error is not
    something the social auth middleware turns into a readable answer.
    """
    if user:
        return None

    email = (details.get("email") or "").lower()
    if email and users_with_email(email).exists():
        raise AuthException(
            backend,
            "An account already uses this email address. Sign in with your password.",
        )
    return None
