import pytest

from apps.account.models import Contact
from apps.account.selectors import SIDEBAR_FOLLOWING_LIMIT, sidebar_following
from apps.images.models import Image


@pytest.mark.django_db
def test_sidebar_following_counts_images_without_a_query_per_person(user, second_user):
    viewer, _ = user
    followed, _ = second_user
    Contact.objects.create(user_from=viewer.profile, user_to=followed.profile)
    Image.objects.create(user=followed, title="One", url="https://example.com/1.png")

    listed = list(sidebar_following(viewer))

    assert [person.images_count for person in listed] == [1]


@pytest.mark.django_db
def test_sidebar_following_leaves_out_staff_accounts(user, staff_user):
    viewer, _ = user
    staff, _ = staff_user
    Contact.objects.create(user_from=viewer.profile, user_to=staff.profile)

    assert list(sidebar_following(viewer)) == []


@pytest.mark.django_db
def test_sidebar_following_stops_at_the_limit(user, make_user):
    viewer, _ = user
    for number in range(SIDEBAR_FOLLOWING_LIMIT + 2):
        followed, _ = make_user(
            f"person{number}", f"person{number}@example.com", "testpass123"
        )
        Contact.objects.create(user_from=viewer.profile, user_to=followed.profile)

    assert len(sidebar_following(viewer)) == SIDEBAR_FOLLOWING_LIMIT
