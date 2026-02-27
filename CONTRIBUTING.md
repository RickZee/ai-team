# Contributing to AI-Team

Thank you for your interest in contributing. This document covers development setup, code style, the PR process, and how to extend agents, tools, and guardrails.

## Development setup

### Prerequisites

- Python 3.11 or 3.12
- [Poetry](https://python-poetry.org/) (or use `uv` with the same `pyproject.toml`)
- OpenRouter API key for full flow (see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md))

### Install

```bash
git clone https://github.com/yourusername/ai-team.git
cd ai-team
poetry install
poetry run pytest   # Sanity check
```

Install with dev dependencies (already included in `poetry install`):

- pytest, pytest-cov, pytest-asyncio, pytest-timeout, pytest-mock
- ruff, black, isort, mypy
- pre-commit (optional)

### Optional: pre-commit

```bash
poetry run pre-commit install
```

Hooks can run ruff, black, and mypy before each commit.

## Code style guide

We use **black**, **ruff**, and **mypy** for consistent, type-checked code.

### Black (formatting)

- Line length: 100 (configured in `pyproject.toml`).
- Run: `poetry run black src/ai_team tests/`

### Ruff (linting)

- Rules: E, F, I, N, W, UP, B, C4, SIM; E501 ignored (line length left to black).
- Run: `poetry run ruff check src/ai_team tests/`
- Auto-fix: `poetry run ruff check --fix src/ai_team tests/`

### isort (import sorting)

- Run: `poetry run isort src/ai_team tests/`

### mypy (type checking)

- Target: Python 3.11.
- Run: `poetry run mypy src/ai_team`
- Config: `warn_return_any`, `warn_unused_configs`, `ignore_missing_imports` in `pyproject.toml`.

Before opening a PR, ensure:

```bash
poetry run black src/ai_team tests/
poetry run ruff check src/ai_team tests/
poetry run mypy src/ai_team
poetry run pytest
```

## PR process and commit messages

1. **Branch:** Create a feature branch from `main` (e.g. `feature/add-xyz`, `fix/issue-123`).
2. **Tests:** Add or update tests as needed; all tests must pass.
3. **Lint/format:** Run black, ruff, and mypy as above.
4. **PR:** Open a pull request against `main` with a clear title and description. Reference any issues.
5. **Review:** Address review comments; maintainers will merge when ready.

### Commit message convention

- Use present tense, imperative mood: “Add feature X”, “Fix parsing of Y”.
- Optional prefix: `feat:`, `fix:`, `docs:`, `test:`, `chore:` for clarity.
- Example: `feat: add security guardrail for file path validation`.

## Testing requirements

- **Unit tests:** Fast, isolated; mock external services. Live under `tests/unit/`.
- **Integration tests:** May hit OpenRouter when `AI_TEAM_USE_REAL_LLM=1`; use fixtures and timeouts. Live under `tests/integration/`.
- **E2E tests:** Full flow when applicable; document any environment assumptions. Live under `tests/e2e/`.

Run with coverage:

```bash
poetry run pytest --cov=src/ai_team --cov-report=term-missing
```

New behavior should be covered by unit and/or integration tests as appropriate.

## Adding new agents, tools, or guardrails

### Adding a new agent

1. **Define the role** in `config/agents.yaml` (goal, backstory, verbose, allow_delegation, etc.).
2. **Implement** in `src/ai_team/agents/` (extend the base agent pattern used by existing agents).
3. **Map to a model** in settings (e.g. `MY_AGENT_MODEL` in `.env` or in the app config).
4. **Wire into a crew** in `src/ai_team/crews/` and reference in the flow if needed.
5. **Document** in [docs/AGENTS.md](docs/AGENTS.md) and add tests.

### Adding a new tool

1. **Implement** the tool in `src/ai_team/tools/` (CrewAI tool interface; use existing file/code/git tools as reference).
2. **Apply guardrails** where relevant (e.g. path validation, code safety) via the guardrail layer.
3. **Attach** to the appropriate agent(s) in the crew or base agent setup.
4. **Document** in [docs/TOOLS.md](docs/TOOLS.md) and add unit tests (and integration tests if it calls external services).

### Adding or changing guardrails

1. **Implement** in `src/ai_team/guardrails/` (behavioral, security, or quality module).
2. **Integrate** into the full guardrail chain (see existing `create_full_guardrail_chain` or equivalent).
3. **Configure** via settings/GuardrailConfig and `.env` if needed.
4. **Document** in [docs/GUARDRAILS.md](docs/GUARDRAILS.md) and add tests in the guardrail test suite.

If you are unsure where a change belongs, open an issue or ask in the PR description.
