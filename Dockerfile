# Styles and vendor assets are built here, not committed: they are generated
# files. Tailwind 4 works out which classes to keep by scanning the project
# itself, so the whole source tree has to be present — a stage with only the
# stylesheet would silently produce a much smaller file.
FROM node:24-alpine AS frontend

WORKDIR /build

COPY package.json package-lock.json ./

RUN npm ci

COPY . .

RUN npm run copy:vendor && npm run build:css


FROM python:3.13-slim AS base

WORKDIR /app

# Only the inner directory: it is the root every import in the project is
# written against (settings, config, apps, core). Adding /app as well made the
# same package reachable under a second name, and a module imported twice under
# two names is two separate objects with two separate copies of its state.
ENV PYTHONPATH=/app/app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

# Installed from the lock file, not from the version ranges in pyproject.toml.
# Installing from the ranges takes whatever is newest on the index at build
# time, so two images built from the same commit a month apart hold different
# libraries — and the versions the tests ran against are not the ones that
# reach production.
RUN uv export --frozen --no-emit-project --format requirements-txt -o /tmp/requirements.txt \
    && uv pip install --system --no-cache -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY . .

# After the source, so a stale copy built on someone's laptop cannot win over
# the one this build just produced.
COPY --from=frontend /build/app/static/css/dist ./app/static/css/dist
COPY --from=frontend /build/app/static/css/vendor ./app/static/css/vendor
COPY --from=frontend /build/app/static/js/vendor ./app/static/js/vendor

EXPOSE 8000


# Development keeps root on purpose: the project is mounted from the host over
# /app, and an unprivileged user could not write into it — no migrations, no
# generated files from inside the container.
FROM base AS dev

RUN uv export --frozen --extra dev --no-emit-project --format requirements-txt -o /tmp/requirements.txt \
    && uv pip install --system --no-cache -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt


FROM base AS web

# The code stays owned by root and is only readable to the account that runs
# it, so a break-in cannot rewrite the application. Everything the processes
# write goes elsewhere: beat's schedule here, uploads to the bucket, logs to
# stdout.
RUN useradd --create-home --shell /usr/sbin/nologin app \
    && install -d -o app -g app /var/lib/celery

USER app


FROM base AS test

RUN uv export --frozen --extra dev --no-emit-project --format requirements-txt -o /tmp/requirements.txt \
    && uv pip install --system --no-cache -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

RUN printf '#!/bin/sh\nset -e\npytest -v --cov --cov-report=term-missing\n' > /usr/local/bin/run-tests \
    && chmod +x /usr/local/bin/run-tests
