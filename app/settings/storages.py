import environ

env = environ.Env()

R2_ACCOUNT_ID = env("R2_ACCOUNT_ID", default="")
R2_BUCKET = env("R2_BUCKET_NAME", default="")
R2_PUBLIC_DOMAIN = env("R2_PUBLIC_DOMAIN", default="")

R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

COMMON_R2_OPTIONS = {
    "endpoint_url": R2_ENDPOINT,
    "access_key": env("R2_ACCESS_KEY_ID", default=""),
    "secret_key": env("R2_SECRET_ACCESS_KEY", default=""),
    "region_name": "auto",
    "signature_version": "s3v4",
    "addressing_style": "virtual",
    "default_acl": None,
    "querystring_auth": False,
}

if R2_PUBLIC_DOMAIN:
    COMMON_R2_OPTIONS["custom_domain"] = R2_PUBLIC_DOMAIN
    COMMON_R2_OPTIONS["url_protocol"] = "https:"

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **COMMON_R2_OPTIONS,
            "bucket_name": R2_BUCKET,
            "location": "media",
            "file_overwrite": False,
        },
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **COMMON_R2_OPTIONS,
            "bucket_name": R2_BUCKET,
            "location": "static",
        },
    },
}
