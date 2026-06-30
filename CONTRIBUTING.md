# Contributing to AI-Team

Thank you for your interest in contributing. This document covers development setup, code style, the PR process, and how to extend agents, tools, and guardrails.

## Development setup

### Prerequisites

- Python 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/) — install: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- OpenRouter API key for full flow (see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md))

### Install

```bash
git clone https://github.com/RickZee/ai-team.git
cd ai-team
uv sync
uv run pytest   # Sanity check
```

Install with dev dependencies (included in `uv sync`):

- pytest, pytest-cov, pytest-asyncio, pytest-timeout, pytest-mock
- ruff, black, isort, mypy
- pre-commit (optional)

### Optional: pre-commit

```bash
uv run pre-commit install
```

Hooks run ruff check (with fix) and ruff format before each commit.

### Before push (matches CI)

```bash
./scripts/pre_push_check.sh           # ruff, mypy, unit tests, pip-audit
./scripts/pre_push_check.sh --main    # + integration tests + frontend build (main)
./scripts/pre_push_check.sh --e2e     # + Playwright web E2E (after UI changes)
```

Runs the same gates as `.github/workflows/ci.yml`. Use `--quick` to skip tests/npm during lint-only iteration.

## Code style guide

We use **black**, **ruff**, and **mypy** for consistent, type-checked code.

### Black (formatting)

- Line length: 100 (configured in `pyproject.toml`).
- Run: `uv run black src/ai_team tests/`

### Ruff (linting)

- Rules: E, F, I, N, W, UP, B, C4, SIM; E501 ignored (line length left to black).
- Run: `uv run ruff check src/ai_team tests/`
- Auto-fix: `uv run ruff check --fix src/ai_team tests/`

### isort (import sorting)

- Run: `uv run isort src/ai_team tests/`

### mypy (type checking)

- Target: Python 3.11.
- Run: `uv run mypy src/ai_team`
- Config: `warn_return_any`, `warn_unused_configs`, `ignore_missing_imports` in `pyproject.toml`.

Before opening a PR, ensure:

```bash
uv run black src/ai_team tests/
uv run ruff check src/ai_team tests/
uv run mypy src/ai_team
uv run pytest
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
uv run pytest --cov=src/ai_team --cov-report=term-missing
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

### Operational guardrails (timeouts, spend, loops)

Beyond content guardrails, the project has **operational** guardrails that bound run
duration, spend, and retry loops. Most are env-configurable — keep these in mind when
running real (paid) backends or writing CI:

| Knob | Default | Effect |
|------|---------|--------|
| `--timeout` (CLI flag) | `900` s | Aborts a hung `run_demo.py` run (exit `124`). `0` disables. |
| `AI_TEAM_RUN_BUDGET_USD` | `5.0` | LangGraph per-run spend ceiling; aborts (`success=False`, exit `1`) when crossed. `0` disables. |
| `AI_TEAM_LANGGRAPH_RECURSION_LIMIT` | `50` | LangGraph graph superstep cap. |

If you add a new retry path, a new backend invoke, or anything that can loop over LLM
calls, make sure it stays bounded by these (or add an equivalent guard) and document it
in [docs/GUARDRAILS.md](docs/GUARDRAILS.md) → *LangGraph backend operational guardrails*.
The spend ceiling is non-retryable by design (`BudgetExceededError` subclasses
`BaseException`); do not catch it in phase nodes.

If you are unsure where a change belongs, open an issue or ask in the PR description.
