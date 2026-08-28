from .base import *

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# The real hasher is slow on purpose, and the suite pays that price on every
# account it makes and every sign-in it performs. Nothing here tests how
# expensive a hash is to compute.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

RATELIMIT_IP_META_KEY = "REMOTE_ADDR"
AXES_ENABLED = False
# Off by default so no test reaches for a real resolver; the tests that cover
# the guard turn it back on and answer the lookup themselves.
BLOCK_PRIVATE_DOWNLOAD_TARGETS = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True

THUMBNAIL_STORAGE = "django.core.files.storage.FileSystemStorage"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
