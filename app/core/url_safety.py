import ipaddress
import socket
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError


def validate_public_url(url):
    """Refuse links that resolve to an address only reachable from inside our
    own network: containers, private ranges, the cloud metadata service.

    The worker fetches whatever address a person puts in a bookmark, so without
    this the platform is a way to knock on doors nobody outside can reach.
    """
    if not settings.BLOCK_PRIVATE_DOWNLOAD_TARGETS:
        return

    host = urlparse(url).hostname
    if not host:
        raise ValidationError("The link has no host to fetch from.")

    try:
        candidates = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValidationError("The link does not resolve to an address.") from exc

    for candidate in candidates:
        address = candidate[4][0]
        try:
            # Everything outside the special-purpose registries is fair game:
            # private ranges, loopback, link-local and the rest are not.
            public = ipaddress.ip_address(address).is_global
        except ValueError:
            public = False
        if not public:
            raise ValidationError("The link points to an address we cannot fetch.")
