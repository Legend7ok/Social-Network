import os
from datetime import timedelta
from pathlib import Path
from django.urls import reverse_lazy

import environ

from .storages import STORAGES

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, ".env"), overwrite=False)

SECRET_KEY = env("SECRET_KEY")

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

LOGIN_URL = "login"
LOGOUT_URL = "logout"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "apps.account.authentication.EmailAuthBackend",
    "social_core.backends.google.GoogleOAuth2",
    "social_core.backends.github.GithubOAuth2",
]

SOCIAL_AUTH_PIPELINE = [
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.user.create_user",
    "apps.account.authentication.create_profile",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",
]

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

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/2",
        "OPTIONS": {
            "socket_connect_timeout": 2,
            "socket_timeout": 2,
        },
    }
}

CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

IMAGE_RANKING_CACHE_KEY = "image_ranking_list"
IMAGE_RANKING_CACHE_TTL = 60 * 5

HOME_CACHE_TTL = 60 * 3

CELERY_BEAT_SCHEDULE = {
    "refresh-image-ranking-cache": {
        "task": "apps.images.tasks.refresh_image_ranking_cache",
        "schedule": timedelta(minutes=4),
    },
}

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

AXES_DISABLE_ACCESS_LOG = True
AXES_FAILURE_LIMIT = 3
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
AXES_LOCKOUT_CALLABLE = "apps.account.views.lockout_view"

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
