from django.conf import settings


def client_ip_address(request):
    """The visitor's address as this deployment sees it.

    Behind the proxy REMOTE_ADDR is the proxy itself, the same value for
    everyone, so anything counting per address has to read the forwarded header
    instead. The rate limiter already does; this hands axes the same answer
    rather than letting the two disagree about who a visitor is.

    Which header that is comes from RATELIMIT_IP_META_KEY, so there is one
    setting to change and not two - development, where nothing proxies and the
    header never arrives, falls back to the address of the connection.
    """
    meta_key = getattr(settings, "RATELIMIT_IP_META_KEY", "REMOTE_ADDR")
    value = request.META.get(meta_key) or request.META.get("REMOTE_ADDR", "")
    # A forwarded header may carry the whole chain; the first entry is the
    # client. nginx here writes a single address, but a proxy in front of it
    # would not.
    return value.split(",")[0].strip() or None
