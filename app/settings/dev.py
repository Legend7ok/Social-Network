import socket
from .base import *

DEBUG = True
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS += ["debug_toolbar"]
MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Uploads land on disk unless the bucket is asked for explicitly, so a fresh
# clone runs with no credentials at all. Set USE_R2=true to develop against the
# real bucket — worth doing before a release, since signed URLs, public
# addresses and overwrite behaviour differ from the local filesystem.
USE_R2 = env.bool("USE_R2", default=False)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Nothing proxies runserver, so the forwarded-for header the rate limiter reads
# in production never arrives and asking for it raises instead of limiting.
RATELIMIT_IP_META_KEY = "REMOTE_ADDR"

# Bookmarking an image served from the machine you develop on is the normal
# case here, and every one of those addresses is private.
BLOCK_PRIVATE_DOWNLOAD_TARGETS = False

STORAGES = {
    **STORAGES,
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Thumbnails follow: sorl cuts them into the default storage unless told
# otherwise, and nothing here tells it otherwise any more.
if not USE_R2:
    STORAGES["default"] = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }

hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
INTERNAL_IPS = [ip[: ip.rfind(".")] + ".1" for ip in ips]

DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: True,
}
