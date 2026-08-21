import pytest
from django.contrib.auth import get_user_model

from apps.account.models import Profile
from apps.images.models import Image


@pytest.fixture
def make_person(db):
    def _make(username, first_name, last_name, **fields):
        person = get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="testpass123",
            first_name=first_name,
            last_name=last_name,
            **fields,
        )
        Profile.objects.create(user=person)
        return person

    return _make


@pytest.fixture
def people(make_person):
    return {
        "dmytro": make_person("tkachenkodm", "Dmytro", "Tkachenko"),
        "maria": make_person("mariapetrova", "Maria", "Petrova"),
        "staff": make_person("adminuser", "Admin", "Root", is_staff=True),
    }


@pytest.fixture
def images(db, user):
    user_obj, _ = user
    described = [
        ("Sunset over the sea", "Calm water and a warm sky"),
        ("Calm morning", "A sunset seen from the window"),
        ("Abstract glass sphere", "Soft translucent bubbles"),
    ]
    return [
        Image.objects.create(
            user=user_obj,
            title=title,
            description=description,
            url="https://example.com/photo.jpg",
        )
        for title, description in described
    ]


@pytest.fixture
def logged_client(client, user):
    user_obj, password = user
    client.login(username=user_obj.username, password=password)
    return client
