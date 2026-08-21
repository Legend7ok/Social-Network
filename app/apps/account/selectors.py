from django.contrib.auth import get_user_model

User = get_user_model()


def public_users():
    """People that may show up anywhere on the public side of the site."""
    return User.objects.filter(is_active=True, is_staff=False, is_superuser=False)
