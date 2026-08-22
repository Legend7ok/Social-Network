def display_name(user):
    """Registration asks for a username only, and social logins may hand over no
    name either, so every place that shows a person needs this fallback."""
    return user.get_full_name() or user.username


def initials(user):
    """Letters for the placeholder an avatar is laid over. Falls back to the
    username so the circle is never empty."""
    letters = f"{user.first_name[:1]}{user.last_name[:1]}".strip()
    return (letters or user.username[:2]).upper()
