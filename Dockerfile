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


FROM base AS web

RUN sed -i 's/\r//' entrypoint.sh && chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]


FROM base AS test

RUN uv pip install --system --no-cache .[dev]

RUN printf '#!/bin/sh\nset -e\npytest -v --cov --cov-report=term-missing\n' > /usr/local/bin/run-tests \
    && chmod +x /usr/local/bin/run-tests
