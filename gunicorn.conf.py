import os

# A fixed number, not the usual "cores × 2 + 1": with the app preloaded every
# process carries its own copy of Django, and on a 16-thread machine that
# formula asks for 33 of them — several gigabytes before a single visitor
# arrives, well past the memory this container is allowed. Five processes of
# two threads each serve far more than this site will ever see; raise
# GUNICORN_WORKERS if a real load ever says otherwise.
DEFAULT_WORKERS = 5

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.getenv("GUNICORN_WORKERS", DEFAULT_WORKERS))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")

timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

capture_output = True
preload_app = True
forwarded_allow_ips = "*"
worker_tmp_dir = "/dev/shm"
