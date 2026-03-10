import pytest
from django.contrib.auth import get_user_model

from .models import Profile


@pytest.fixture
def user(db):
    user_model = get_user_model()
    password = "testpass123"
    user_obj = user_model.objects.create_user(
        username="alice",
        first_name="Alice",
        email="alice@example.com",
        password=password,
    )
    Profile.objects.create(user=user_obj)
    return user_obj, password
