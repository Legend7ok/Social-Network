FROM python:3.13-slim AS base

WORKDIR /app

ENV PYTHONPATH=/app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

RUN uv pip install --system --no-cache .

COPY . .


FROM base AS web

RUN sed -i 's/\r//' entrypoint.sh && chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]


FROM base AS test

RUN printf '#!/bin/sh\nset -e\npytest -v\n' > /usr/local/bin/run-tests \
    && chmod +x /usr/local/bin/run-tests
