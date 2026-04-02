# AI-Team project conventions (Claude Agent SDK)

This file is loaded into Claude Code sessions via repository context. Keep it concise; expand static guidance in `docs/` and dynamic retrieval via RAG when enabled.

## Engineering standards

- Python 3.11+ with type hints on public APIs and Google-style docstrings for non-trivial modules.
- Formatting: Black; lint: Ruff (zero warnings in CI). Types: mypy on `src/ai_team` (see `pyproject.toml` overrides).
- Use **structlog** for logging; do not use bare `print()` in library code.
- Configuration via **Pydantic Settings** / environment variables; never commit secrets (no `.env` in git).
- Paths: validate workspace boundaries; reject `..` traversal and sensitive filenames (`.env`, credentials) for automated writes.

## Security

- No `eval()`, `exec()`, or `os.system()` in tools or generated automation.
- Subprocess: use argument lists, `shell=False`.
- YAML: `yaml.safe_load` only (never unsafe load).

## Testing

- Pytest for unit and integration tests; prefer mocks for LLM and external APIs in CI.
- New tools and guardrails require adversarial and happy-path tests per project rules.

## Multi-agent workspace layout

Orchestration backends use a per-run workspace (often `./workspace/<id>/`) with:

- `docs/` — requirements, architecture, summaries, `test_results.json`
- `src/` — generated application code
- `tests/` — generated or augmented tests
- `logs/` — `phases.jsonl`, `costs.jsonl`, `audit.jsonl`, `session.json`

Agents coordinate through these paths (file-based handoff), not a shared in-memory state object.

## Backends

- **crewai** — OpenRouter / LiteLLM; existing CrewAI flows.
- **langgraph** — OpenRouter; graph checkpointing and streaming.
- **claude-agent-sdk** — Anthropic API key; Claude Agent SDK + Claude Code runtime; native MCP and session persistence.

Choose the backend explicitly (`--backend`); do not assume OpenRouter keys work for the Claude Agent SDK backend.
