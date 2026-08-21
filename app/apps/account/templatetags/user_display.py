from django import template

from apps.account import display

register = template.Library()


# Templates may address someone who is not there: ranking.html draws all three
# podium places even with fewer images and Django hands a missing variable over
# as an empty string, while public pages carry a visitor who is not signed in.
# Neither has a name to show, and neither should bring the page down.
def _is_a_person(value):
    return getattr(value, "is_authenticated", False)


@register.filter
def display_name(user):
    return display.display_name(user) if _is_a_person(user) else ""


@register.filter
def initials(user):
    return display.initials(user) if _is_a_person(user) else ""
