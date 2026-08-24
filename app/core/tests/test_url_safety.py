import socket

import pytest
from django.core.exceptions import ValidationError

from core.url_safety import validate_public_url


@pytest.fixture(autouse=True)
def guard_on(settings):
    settings.BLOCK_PRIVATE_DOWNLOAD_TARGETS = True


def resolve_to(*addresses):
    return lambda *args, **kwargs: [
        (socket.AF_INET, None, None, "", (address, 0)) for address in addresses
    ]


def test_accepts_a_host_resolving_to_a_public_address(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", resolve_to("93.184.216.34"))
    validate_public_url("https://example.com/photo.jpg")


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.5",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "0.0.0.0",
        "::1",
    ],
)
def test_rejects_addresses_reachable_only_from_inside(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", resolve_to(address))
    with pytest.raises(ValidationError):
        validate_public_url("https://internal.example.com/photo.jpg")


def test_rejects_a_host_that_answers_with_a_private_address_as_well(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", resolve_to("93.184.216.34", "10.0.0.5"))
    with pytest.raises(ValidationError):
        validate_public_url("https://example.com/photo.jpg")


def test_rejects_a_host_that_does_not_resolve(monkeypatch):
    def fail(*args, **kwargs):
        raise socket.gaierror("unknown host")

    monkeypatch.setattr(socket, "getaddrinfo", fail)
    with pytest.raises(ValidationError):
        validate_public_url("https://nowhere.example.com/photo.jpg")


def test_rejects_a_link_without_a_host():
    with pytest.raises(ValidationError):
        validate_public_url("https:///photo.jpg")


def test_looks_nothing_up_when_the_guard_is_off(monkeypatch, settings):
    settings.BLOCK_PRIVATE_DOWNLOAD_TARGETS = False

    def fail(*args, **kwargs):
        raise AssertionError("the resolver must not be touched")

    monkeypatch.setattr(socket, "getaddrinfo", fail)
    validate_public_url("http://127.0.0.1/photo.jpg")
