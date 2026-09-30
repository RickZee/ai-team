---
description: Project identity and tech stack for ai-team (CrewAI multi-agent system)
alwaysApply: true
---

# AI-Team Project Context

You are working on **ai-team**: one nine-agent software team (Manager, Product Owner,
Architect, Backend/Frontend/Fullstack Developers, DevOps, Cloud Engineer, QA) that runs on
three orchestration frameworks behind one `Backend` protocol, plus the harness and eval
suite that make those runs comparable. The harness is the product; see `README.md`.

## Technology Stack (source of truth: `pyproject.toml`, `uv.lock`)

- **Python** 3.11–3.13, managed with **uv**
- **Backends:** CrewAI (`backends/crewai_backend/`), LangGraph (`backends/langgraph_backend/`),
  Claude Agent SDK (`backends/claude_agent_sdk_backend/`)
- **Models:** OpenRouter via LiteLLM for CrewAI/LangGraph (role → model in `config/models.py`),
  Anthropic API for the Claude Agent SDK. No local Ollama path.
- **Runtime:** Pydantic v2 + pydantic-settings, structlog, FastAPI + uvicorn, React/Vite UI
- **Tooling:** pytest, Ruff (format + lint), mypy. No Black, no isort.

## Project Structure (abbreviated)

- `src/ai_team/` — `core/` (Backend protocol), `backends/`, `harness/`, `tools/`, `guardrails/`,
  `config/`, `memory/`, `models/`, `ui/web/`
- `evals/` — trace store, failure taxonomy, deterministic checks, Tier A replay gate
- `tests/` — unit/ (CI), integration/, conformance/, e2e/, performance/
- `course/` — the six-week course; `docs/` — reference docs, journal, posts
- `.kiro/specs/<id>/` — Kiro-style specs (`README` → `requirements` → `design` →
  `tasks`). `tasks.md` is a living checklist; see the `kiro-specs` rule.
