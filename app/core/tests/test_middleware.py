import json

import pytest
from django.http import JsonResponse
from django.test import RequestFactory

from core.exceptions import RedisUnavailableError, ServiceUnavailableError
from core.middleware import ServiceUnavailableMiddleware


@pytest.fixture
def mw():
    return ServiceUnavailableMiddleware(get_response=lambda r: None)


@pytest.fixture
def factory():
    return RequestFactory()


@pytest.mark.django_db
def test_html_request_returns_503(mw, factory):
    request = factory.get("/")
    response = mw.process_exception(request, RedisUnavailableError("Redis unavailable"))
    assert response.status_code == 503


@pytest.mark.django_db
def test_json_request_returns_json_503(mw, factory):
    request = factory.get("/", HTTP_ACCEPT="application/json")
    response = mw.process_exception(request, RedisUnavailableError("Redis unavailable"))
    assert response.status_code == 503
    assert isinstance(response, JsonResponse)
    data = json.loads(response.content)
    assert "detail" in data


def test_ignores_other_exceptions(mw, factory):
    request = factory.get("/")
    result = mw.process_exception(request, ValueError("unrelated"))
    assert result is None


@pytest.mark.django_db
def test_catches_any_service_unavailable_subclass(mw, factory):
    class CustomError(ServiceUnavailableError):
        pass

    request = factory.get("/")
    response = mw.process_exception(request, CustomError("custom"))
    assert response.status_code == 503
