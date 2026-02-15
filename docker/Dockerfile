# -----------------------------------------------------------------------------
# Stage 1: Builder — install deps and project with uv (cache-friendly layers)
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# System deps for building wheels and for git (e.g. git-based deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv from official image (pin version in production: e.g. /uv:0.10.2)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependencies only — cached unless pyproject.toml / uv.lock change
COPY pyproject.toml uv.lock ./
ENV UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

# Project code — then sync project into env
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# -----------------------------------------------------------------------------
# Stage 2: Runtime — minimal image, non-root user, Gradio on 8501
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for running the app
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

WORKDIR /app

# Copy virtual env and app code from builder
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --from=builder --chown=app:app /app/ui /app/ui
COPY --from=builder --chown=app:app /app/pyproject.toml /app/pyproject.toml

ENV PATH="/app/.venv/bin:$PATH" \
    GRADIO_SERVER_NAME="0.0.0.0" \
    GRADIO_SERVER_PORT="8501"

USER app

EXPOSE 8501

# Launch Gradio UI (port 8501)
CMD ["python", "ui/app.py"]
