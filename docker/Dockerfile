# Multi-stage build for ai-team web UI (FastAPI + React)
# Stage 1: builder — install dependencies with uv
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src

RUN uv sync --frozen --no-dev

# Stage 2: runtime — minimal image with non-root user
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash aiteam

WORKDIR /app

COPY --from=builder /app/.venv .venv
COPY --from=builder /app/src ./src
COPY pyproject.toml uv.lock ./

ENV PATH="/app/.venv/bin:${PATH}"

RUN chown -R aiteam:aiteam /app
USER aiteam

EXPOSE 8421

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:8421/api/backends || exit 1

ENTRYPOINT ["ai-team-web"]
