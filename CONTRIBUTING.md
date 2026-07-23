# Contributing to AI-Team

Thank you for your interest in contributing. This document covers development setup, code style, the PR process, and how to extend agents, tools, guardrails, and backends.

## What this project is (before you start)

AI-Team runs the **same nine-agent software team across three orchestration backends** — CrewAI, LangGraph, and the Claude Agent SDK — behind one `Backend` protocol (`src/ai_team/core/backend.py`), so an identical brief can be run through each and compared on correctness, wall-clock time, and cost. Two consequences for contributors:

- **Most changes should be backend-aware.** A guardrail, tool, or agent change that only works on one backend is usually incomplete. If a change is deliberately backend-specific, say so in the PR.
- **Comparison claims need data, not a single run.** Same-config runs vary widely (the smoke brief has ranged 6m50s → 10m41s within one hour). Any claim about a backend's speed, cost, or reliability should come from a batch of runs — see [`scripts/run_smoke_batch.py`](scripts/run_smoke_batch.py) and the n=5 note under *PR process* below.

## Development setup

### Prerequisites

- Python 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/) — install: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **API keys, per backend** (see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)):
  - `OPENROUTER_API_KEY` — CrewAI and LangGraph backends.
  - `ANTHROPIC_API_KEY` — Claude Agent SDK backend.
  - You only need the key for the backend(s) you plan to run. Unit tests need neither (they mock the LLM).

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

1. **Branch:** Create a feature branch from `main` (e.g. `feature/add-xyz`, `fix/issue-123`). Do not commit directly to `main`.
2. **Tests:** Add or update tests as needed; all tests must pass.
3. **Lint/format:** Run black, ruff, and mypy as above.
4. **Pre-push gate:** Run `./scripts/pre_push_check.sh` (add `--main` when targeting `main`). It runs the same gates as CI — a green local run is expected before you open the PR.
5. **PR:** Open a pull request against `main` with a clear title and description. Reference any issues.
6. **Review:** Address review comments; maintainers will merge when ready.

### If your PR makes a backend-comparison claim

Anything of the form "backend X is faster / cheaper / more reliable than Y" needs evidence from a batch, not a single run, because same-config variance is large. Two rules the batch runner now enforces for you:

- **Control the model.** The default profile is mixed-model (deepseek vs Claude), so its numbers compare framework+model bundles, not frameworks. Use `--team smoke-claude` to pin one model across backends.
- **Don't rank on the canary.** The smoke demo is a wiring check. Use `--demo demos/02_todo_app` for a claim you intend to generalize.

```bash
uv run python scripts/run_smoke_batch.py --n 5 --team smoke-claude --demo demos/02_todo_app
```

The runner prints a Wilson confidence interval per backend and refuses to declare a winner when intervals overlap ("no significant difference at this n"). Paste its output into the PR. Verdicts have a shelf life here — a claim that held at n=1 reversed at n=5 more than once, and several "n=5 winners" don't survive their own interval.

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

1. **Define the role** in `config/agents.yaml` (role, goal, backstory) — this file is shared across all three backends.
2. **Map it to a model** by adding the role to `ENV_MODELS` in [`src/ai_team/config/models.py`](src/ai_team/config/models.py) (keyed by environment tier → role → `RoleModelConfig`). There is no per-agent `.env` model variable; model assignment lives in `models.py`, with optional per-run overrides in `config/team_profiles.yaml`. See [docs/MODELS.md](docs/MODELS.md).
3. **Add it to a team profile** in `config/team_profiles.yaml` so a profile actually rosters the new role.
4. **Wire it into the backends that need it:** the CrewAI path uses `src/ai_team/agents/` + `src/ai_team/crews/`; LangGraph and the Claude SDK consume the same `TeamProfile` roster and prompts. Keep the role's behavior consistent across backends, or document the difference.
5. **Document** the role in [docs/AGENTS.md](docs/AGENTS.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and add tests.

### Adding a new tool

1. **Implement** the tool in `src/ai_team/tools/` (CrewAI tool interface; use existing file/code/git tools as reference).
2. **Apply guardrails** where relevant (e.g. path validation, code safety) via the guardrail layer.
3. **Attach** to the appropriate agent(s) in the crew or base agent setup.
4. **Document** the tool alongside the others in [`src/ai_team/tools/`](src/ai_team/tools/) and add unit tests (and integration tests if it calls external services).

### Adding or changing guardrails

1. **Implement** in `src/ai_team/guardrails/` (behavioral, security, or quality module).
2. **Integrate** into the full guardrail chain (see existing `create_full_guardrail_chain` or equivalent).
3. **Configure** via settings/GuardrailConfig and `.env` if needed.
4. **Document** in [docs/GUARDRAILS.md](docs/GUARDRAILS.md) and add tests in the guardrail test suite.

### Adding a new backend

A backend is any orchestration engine that can turn a brief into a delivered project. To add one (e.g. AutoGen, Bedrock Agents):

1. **Implement the `Backend` protocol** (`src/ai_team/core/backend.py`): `run(description, team, env) → ProjectResult` and `stream(...) → AsyncIterator[StreamEvent]`. Return a normalized `ProjectResult` so the CLI, dashboard, and comparison scripts don't need to know which engine ran.
2. **Register it** by adding a branch in `get_backend()` in [`src/ai_team/backends/registry.py`](src/ai_team/backends/registry.py) — it dispatches by name (`crewai | langgraph | claude-agent-sdk`).
3. **Consume the shared `TeamProfile`**, don't hard-code a roster — the whole point is that `--team` selects the same agents for every backend.
4. **Honor the deliverable contract.** Generated files land in the per-run workspace (`workspace_dir/<id>/`), and profiles that include the `deployment` phase must produce a non-empty root `README.md`. Enforcement is shared: `deployment_artifacts_guardrail()` runs from the common post-run path for *every* backend, so a new backend is checked automatically (it's warn-only).
5. **Bound the loops.** Any path that can retry or loop over LLM calls needs a spend/timeout guard (see the operational guardrails below).
6. **Add it to the comparison surface** — the smoke batch and the docs tables — and run n≥5 so its row is real data, not a single run.

### Operational guardrails (timeouts, spend, loops)

Beyond content guardrails, the project has **operational** guardrails that bound run
duration, spend, and retry loops. Most are env-configurable — keep these in mind when
running real (paid) backends or writing CI:

| Knob | Default | Effect |
|------|---------|--------|
| `--timeout` (CLI flag) | `900` s | Aborts a hung `run_demo.py` run (exit `124`). `0` disables. |
| `AI_TEAM_MAX_COST_PER_RUN` | `5.0` | Pre-run estimate ceiling; aborts before the run if the estimate exceeds it. |
| `AI_TEAM_RUN_BUDGET_USD` | `5.0` | Runtime spend guard; non-retryable abort once *actual* spend crosses it (`success=False`, exit `1`). `0` disables. |
| `CREWAI_HARD_TIMEOUT_SECONDS` | `900` | Wall-clock kill deadline for the CrewAI subprocess (it can ignore its own internal timeout; this is the hard outer kill). |
| `AI_TEAM_LANGGRAPH_RECURSION_LIMIT` | `50` | LangGraph graph superstep cap. |

Keep this table in sync with the *Configuration reference* in [README.md](README.md#configuration-reference) when you add or change a knob.

If you add a new retry path, a new backend invoke, or anything that can loop over LLM
calls, make sure it stays bounded by these (or add an equivalent guard) and document it
in [docs/GUARDRAILS.md](docs/GUARDRAILS.md) → *LangGraph backend operational guardrails*.
The spend ceiling is non-retryable by design (`BudgetExceededError` subclasses
`BaseException`); do not catch it in phase nodes.

If you are unsure where a change belongs, open an issue or ask in the PR description.
