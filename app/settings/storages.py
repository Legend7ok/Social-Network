import environ

env = environ.Env()


def build_storages(*, required):
    """Storage configuration for the Cloudflare R2 bucket.

    Built by a call rather than at import time, so the variables are read only
    after the .env file has been loaded - importing this module happens before
    that.

    With required=True a missing key stops the process at startup, naming the
    variable. Production asks for that: the alternative is a site that starts,
    serves pages and only falls over when someone uploads their first picture.
    Development leaves them optional and writes to disk instead.
    """
    read = env if required else (lambda name: env(name, default=""))

    account_id = read("R2_ACCOUNT_ID")
    bucket = read("R2_BUCKET_NAME")
    public_domain = env("R2_PUBLIC_DOMAIN", default="")

    options = {
        "endpoint_url": f"https://{account_id}.r2.cloudflarestorage.com",
        "access_key": read("R2_ACCESS_KEY_ID"),
        "secret_key": read("R2_SECRET_ACCESS_KEY"),
        "region_name": "auto",
        "signature_version": "s3v4",
        "addressing_style": "virtual",
        "default_acl": None,
        "querystring_auth": False,
    }

    # Optional: without it files are served from the bucket's own endpoint.
    if public_domain:
        options["custom_domain"] = public_domain
        options["url_protocol"] = "https:"

    return {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                **options,
                "bucket_name": bucket,
                "location": "media",
                "file_overwrite": False,
            },
        },
        # Manifest, not plain: it stores every file under a name carrying the
        # hash of its contents, so a new release is a new address and no
        # browser can serve yesterday's stylesheet from its cache. With one
        # fixed name there is nothing to tell the two apart, and a deploy
        # leaves people on the old styles and the old scripts until their
        # browser decides to ask again.
        "staticfiles": {
            "BACKEND": "storages.backends.s3.S3ManifestStaticStorage",
            "OPTIONS": {
                **options,
                "bucket_name": bucket,
                "location": "static",
            },
        },
    }
