import pytest
from django.db import IntegrityError

from apps.account.models import Contact


@pytest.mark.django_db
def test_following_the_same_person_twice_is_refused(user, second_user):
    """The view reads before it writes, and two requests can both read nothing
    at the same moment; the database is what settles it."""
    follower, _ = user
    target, _ = second_user
    Contact.objects.create(user_from=follower.profile, user_to=target.profile)

    with pytest.raises(IntegrityError):
        Contact.objects.create(user_from=follower.profile, user_to=target.profile)


@pytest.mark.django_db
def test_the_other_direction_stays_allowed(user, second_user):
    """Following is one-way: the pair is ordered, so two people may follow each
    other and that is two rows, not a duplicate."""
    follower, _ = user
    target, _ = second_user
    Contact.objects.create(user_from=follower.profile, user_to=target.profile)
    Contact.objects.create(user_from=target.profile, user_to=follower.profile)

    assert Contact.objects.count() == 2
