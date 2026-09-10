from django.test import RequestFactory

from core.ip import client_ip_address


def test_reads_the_forwarded_address_when_that_is_the_configured_key(settings):
    """What production does: behind the proxy REMOTE_ADDR is the proxy itself,
    the same value for every visitor, so the header is the only place the
    person's own address survives."""
    settings.RATELIMIT_IP_META_KEY = "HTTP_X_FORWARDED_FOR"
    request = RequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="203.0.113.7", REMOTE_ADDR="172.18.0.5"
    )

    assert client_ip_address(request) == "203.0.113.7"


def test_takes_the_first_address_of_a_chain(settings):
    """Another proxy in front would append to the header; the client is the
    entry it starts with."""
    settings.RATELIMIT_IP_META_KEY = "HTTP_X_FORWARDED_FOR"
    request = RequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="203.0.113.7, 172.18.0.5", REMOTE_ADDR="172.18.0.5"
    )

    assert client_ip_address(request) == "203.0.113.7"


def test_falls_back_to_the_connection_when_the_header_is_missing(settings):
    """Development, where nothing proxies and the header never arrives."""
    settings.RATELIMIT_IP_META_KEY = "HTTP_X_FORWARDED_FOR"
    request = RequestFactory().get("/", REMOTE_ADDR="127.0.0.1")

    assert client_ip_address(request) == "127.0.0.1"


def test_reads_the_connection_when_that_is_the_configured_key(settings):
    settings.RATELIMIT_IP_META_KEY = "REMOTE_ADDR"
    request = RequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="203.0.113.7", REMOTE_ADDR="127.0.0.1"
    )

    assert client_ip_address(request) == "127.0.0.1"


def test_answers_none_when_there_is_no_address_at_all(settings):
    """axes accepts an unknown address; handing it an empty string would count
    every such request as one and the same visitor."""
    settings.RATELIMIT_IP_META_KEY = "REMOTE_ADDR"
    request = RequestFactory().get("/")
    request.META.pop("REMOTE_ADDR", None)

    assert client_ip_address(request) is None
