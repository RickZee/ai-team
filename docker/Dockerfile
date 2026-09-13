# Dockerfile — web UI (FastAPI + React)

# Stage 1: frontend
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY src/ai_team/ui/web/frontend/package.json src/ai_team/ui/web/frontend/package-lock.json ./
RUN npm ci
COPY src/ai_team/ui/web/frontend/ ./
RUN npm run build

# Stage 2: Python builder
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

# Stage 3: runtime — no compiler toolchain
FROM python:3.11-slim AS runtime
# git: agents commit inside per-run workspaces
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --shell /bin/bash aiteam
WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY --from=builder /app/src ./src
COPY --from=frontend /frontend/dist ./src/ai_team/ui/web/frontend/dist
COPY pyproject.toml uv.lock README.md ./
ENV PATH="/app/.venv/bin:${PATH}"
RUN chown -R aiteam:aiteam /app
USER aiteam
EXPOSE 8421
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:8421/api/health || exit 1
ENTRYPOINT ["ai-team-web"]
