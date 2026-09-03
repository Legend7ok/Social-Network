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

ENV PYTHONPATH=/app:/app/app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

RUN uv pip install --system --no-cache .

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

RUN uv pip install --system --no-cache .[dev]


FROM base AS web

# The code stays owned by root and is only readable to the account that runs
# it, so a break-in cannot rewrite the application. Everything the processes
# write goes elsewhere: beat's schedule here, uploads to the bucket, logs to
# stdout.
RUN useradd --create-home --shell /usr/sbin/nologin app \
    && install -d -o app -g app /var/lib/celery

USER app


FROM base AS test

RUN uv pip install --system --no-cache .[dev]

RUN printf '#!/bin/sh\nset -e\npytest -v --cov --cov-report=term-missing\n' > /usr/local/bin/run-tests \
    && chmod +x /usr/local/bin/run-tests
