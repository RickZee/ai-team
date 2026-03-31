# Multi-stage build for ai-team Gradio UI
# Stage 1: builder — install Poetry and dependencies
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV POETRY_VERSION=1.8.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_IN_PROJECT=true
ENV PATH="${POETRY_HOME}/bin:${PATH}"

RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

COPY pyproject.toml ./
RUN poetry lock --no-update && poetry install --no-dev --no-interaction --no-ansi --no-root

COPY src ./src
COPY pyproject.toml ./
RUN poetry install --no-dev --no-interaction --no-ansi

# Stage 2: runtime — minimal image with non-root user
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_IN_PROJECT=true
ENV PATH="${POETRY_HOME}/bin:${PATH}"

RUN curl -sSL https://install.python-poetry.org | python3 -

RUN useradd --create-home --shell /bin/bash aiteam

WORKDIR /app

COPY --from=builder /app/.venv .venv
COPY --from=builder /app/src ./src
COPY --from=builder /app/pyproject.toml ./

ENV PATH="/app/.venv/bin:${PATH}" \
    GRADIO_SERVER_NAME=0.0.0.0

RUN chown -R aiteam:aiteam /app
USER aiteam

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:7860/ || exit 1

ENTRYPOINT ["poetry", "run", "ai-team-ui"]
