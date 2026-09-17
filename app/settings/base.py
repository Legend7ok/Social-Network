import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from django.urls import reverse_lazy

import environ

from core.redis_guard import GuardedConnection

from .storages import build_storages

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, ".env"), overwrite=False)

SECRET_KEY = env("SECRET_KEY")

# Keys stay optional here; production demands them, see prod.py.
STORAGES = build_storages(required=False)

INSTALLED_APPS = [
    "apps.account",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "social_django",
    "apps.images",
    "apps.actions",
    "apps.comments",
    "apps.search",
    "sorl.thumbnail",
    "axes",
    "rest_framework",
    "drf_spectacular",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.ServiceUnavailableMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.RatelimitMiddleware",
    # Without this every social login failure is a server error, including the
    # ordinary one: closing the provider's window instead of allowing access.
    "social_django.middleware.SocialAuthExceptionMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "app" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_url",
                "core.context_processors.thumbnails",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}",
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "app" / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media/"

# Max size for user-uploaded files (kept below nginx client_max_body_size 10M so
# the friendly form error fires before nginx returns a raw 413).
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB

# Weight alone does not bound the work: a few compressed megabytes can hold a
# hundred megapixels, and decoding one costs about three bytes per pixel.
# Pillow refuses around 89 MP on its own, so the cap sits just under it.
MAX_IMAGE_PIXELS = 80_000_000  # 80 MP

# Bookmarked links are fetched by the worker from inside the network, so by
# default it may only reach addresses the rest of the world can reach too.
BLOCK_PRIVATE_DOWNLOAD_TARGETS = True

LOGIN_URL = "login"
LOGOUT_URL = "logout"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "apps.account.authentication.EmailOrUsernameBackend",
    "social_core.backends.google.GoogleOAuth2",
    "social_core.backends.github.GithubOAuth2",
]

SOCIAL_AUTH_PIPELINE = [
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    # Hand the social login to the account that already owns this address
    # instead of creating a second one, which the unique email index refuses.
    # Safe with these two providers only because both hand over an address the
    # person has proven they control: Google verifies it, GitHub only lets a
    # verified address be the primary one.
    "social_core.pipeline.social_auth.associate_by_email",
    # The step above joins active accounts only; this one turns the leftovers —
    # an address held by a disabled account — into a readable refusal instead of
    # a unique-index error nobody catches.
    "apps.account.pipeline.refuse_a_taken_address",
    "social_core.pipeline.user.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",
]

# Store the address the same way the forms do, so one person keeps one row.
SOCIAL_AUTH_FORCE_EMAIL_LOWERCASE = True

# Where the middleware above sends someone whose social login went wrong; the
# reason arrives as a flash message the login page already renders.
SOCIAL_AUTH_LOGIN_ERROR_URL = "login"

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = env(
    "SOCIAL_AUTH_GOOGLE_OAUTH2_KEY", default="dummy-key"
)
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = env(
    "SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET", default="dummy-secret"
)

SOCIAL_AUTH_GITHUB_KEY = env("SOCIAL_AUTH_GITHUB_KEY", default="dummy-key")
SOCIAL_AUTH_GITHUB_SECRET = env("SOCIAL_AUTH_GITHUB_SECRET", default="dummy-secret")

SITE_URL = env("SITE_URL", default="http://localhost:8000")

ABSOLUTE_URL_OVERRIDES = {
    "auth.user": lambda u: reverse_lazy("user_detail", args=[u.username]),
}

REDIS_HOST = env("REDIS_HOST", default="localhost")
REDIS_PORT = env.int("REDIS_PORT", default=6379)
REDIS_DB = env.int("REDIS_DB", default=0)
REDIS_PASSWORD = env("REDIS_PASSWORD", default="")

# Quoted, because a password is allowed characters that mean something inside a
# URL. Everything that talks to Redis goes through here, so the credentials
# cannot be forgotten in one place and set in another.
_redis_auth = f":{quote(REDIS_PASSWORD, safe='')}@" if REDIS_PASSWORD else ""


def redis_url(db):
    return f"redis://{_redis_auth}{REDIS_HOST}:{REDIS_PORT}/{db}"


# Redis answers in fractions of a millisecond, so a quarter of a second is
# already far more patience than a healthy one ever needs. The old two seconds
# only ever mattered when Redis was down - and then every one of the dozens of
# lookups a page makes paid them, which is what pushed those pages past the
# proxy's limit instead of quietly serving them uncached.
REDIS_TIMEOUT = 0.25

# django-redis rather than Django's own backend for one reason: it can swallow
# a broken connection instead of raising. Nothing here depends on the cache for
# correctness - thumbnails, rate limits and API throttling all survive without
# it - so a dead Redis must not turn every page into an error. Every swallowed
# failure is written to the log, otherwise the site would quietly run uncached
# and nobody would know.
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": redis_url(2),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "IGNORE_EXCEPTIONS": True,
            "SOCKET_CONNECT_TIMEOUT": REDIS_TIMEOUT,
            "SOCKET_TIMEOUT": REDIS_TIMEOUT,
            # Stops dialling once Redis is known to be down; see core.redis_guard.
            "CONNECTION_POOL_KWARGS": {"connection_class": GuardedConnection},
        },
    }
}

DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True

CELERY_BROKER_URL = redis_url(1)
CELERY_RESULT_BACKEND = redis_url(1)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Views are buffered in Redis and flushed here; the interval is the worst-case
# amount of view data a Redis outage can cost us.
CELERY_BEAT_SCHEDULE = {
    "flush-image-views": {
        "task": "apps.images.tasks.flush_image_views",
        "schedule": timedelta(minutes=1),
    },
}

# Write the schedule file after every task sent instead of every few minutes.
# That file's timestamp is what the container's health check reads, and on the
# default interval a beat that died a minute ago still looks alive.
CELERY_BEAT_SYNC_EVERY = 1

FEED_ACTIONS_PER_PAGE = 10
IMAGES_PER_PAGE = 6
USERS_PER_PAGE = 10
COMMENTS_PER_PAGE = 10
REPLIES_PER_PAGE = 10

SEARCH_MIN_QUERY_LENGTH = 2
SEARCH_MAX_QUERY_LENGTH = 100
SEARCH_IMAGES_PER_PAGE = 6
SEARCH_PEOPLE_PER_PAGE = 10
SEARCH_RATE = "50/m"

THUMBNAIL_KVSTORE = "sorl.thumbnail.kvstores.cached_db_kvstore.KVStore"
THUMBNAIL_CACHE = "default"

# Centralized thumbnail geometries - single source of truth.
# Templates read these via the `core.context_processors.thumbnails` processor
# (exposed as `THUMBS`); the Celery pre-generation task imports the same dict,
# so generated sizes always match what the templates request (no cache-key drift).
THUMBNAILS = {
    "content_card": "640x480",  # 4:3 crop - image list, profile grid, ranking top-3, feed banner
    "content_square": "200x200",  # 1:1 crop - detail "More from", feed compact like, ranking rows
    "detail_main": "640",  # width only, no crop - main image on the detail page
    "avatar_sm": "48x48",  # crop - author chip in image cards, ranking top-3 avatars
    "avatar_md": "80x80",  # crop - navbar, sidebars, feed, detail author, liked_by, dropdowns, user cards, edit
    "avatar_lg": "192x192",  # crop - main profile avatar
}

RATELIMIT_IP_META_KEY = "HTTP_X_FORWARDED_FOR"

# With the cache swallowing failures the limiter gets no count back, and its
# default reaction is to refuse everyone - a dead Redis would lock the whole
# site out of posting. Let requests through instead: sign-in stays protected
# either way, because axes counts attempts in the database.
RATELIMIT_FAIL_OPEN = True

AXES_DISABLE_ACCESS_LOG = True
AXES_FAILURE_LIMIT = 3
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
AXES_LOCKOUT_CALLABLE = "apps.account.views.lockout_view"
# Without this axes reads REMOTE_ADDR, which behind the proxy is the proxy -
# one address for every visitor, and a lockout parameter that says nothing.
AXES_CLIENT_IP_CALLABLE = "core.ip.client_ip_address"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "like": "30/min",
        "follow": "20/min",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Social Network API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
