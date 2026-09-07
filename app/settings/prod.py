from .base import *

DEBUG = False
# localhost is always allowed: the container's own health check asks for the
# health endpoint over the loopback address, and a name it may not use makes
# the container look dead while the site serves everyone else fine.
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS") + ["localhost"]
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

# Every picture and every static file lives in the bucket, so a missing key is
# not a degraded mode — it is a broken site. Fail on startup, naming the
# variable, instead of on the first upload.
STORAGES = build_storages(required=True)

# No fallback here. The shared default is a file-based sqlite database, which
# production would take up silently: the site starts, serves an empty world and
# loses everything with the container.
DATABASES = {"default": env.db("DATABASE_URL")}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Security: Django owns these (nginx is a pure reverse proxy, static/media on R2).
# Keeping them here means they are versioned, reviewed and validated by
# `manage.py check --deploy`; the duplicate add_header lines were removed from nginx.
#
# One switch for running the production stack on this machine over plain http —
# no certificate, no tunnel. It turns off three things at once, because turning
# off fewer leaves a site that looks up but cannot be used: the redirect to
# https, the year-long instruction to browsers never to speak http to this host
# again, and the flag that stops cookies from travelling over http, without
# which nobody can sign in. Named to say what it is: this must never be set on
# a server.
INSECURE_LOCAL_HTTP = env.bool("INSECURE_LOCAL_HTTP", default=False)

SECURE_SSL_REDIRECT = not INSECURE_LOCAL_HTTP

# The health check speaks plain http from inside the container; without this it
# would get a redirect to https and read it as a failure. Matched against the
# path with the leading slash stripped.
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]

SESSION_COOKIE_SECURE = not INSECURE_LOCAL_HTTP
CSRF_COOKIE_SECURE = not INSECURE_LOCAL_HTTP
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_HSTS_SECONDS = 0 if INSECURE_LOCAL_HTTP else 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# Logging: app loggers use __name__ (core.*, apps.*); a single stdout handler on
# the root logger collects them so the container runtime captures everything
# (`docker logs`). Without this, our warning/error calls (redis/celery hardening,
# download_image) vanish into Django's default config.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# beat keeps the time of the last run in a file, by default next to the code —
# which the account running it cannot write to. The directory below is created
# for that account in the image.
CELERY_BEAT_SCHEDULE_FILENAME = "/var/lib/celery/celerybeat-schedule"

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.resend.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "resend"
EMAIL_HOST_PASSWORD = env("RESEND_API_KEY")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
SERVER_EMAIL = env("SERVER_EMAIL")
