# Contributing to AI-Team

Thank you for your interest in contributing. This document covers development setup, code style, the PR process, and how to extend agents, tools, guardrails, and backends.

## What this project is (before you start)

AI-Team runs the **same nine-agent software team across three orchestration backends** — CrewAI, LangGraph, and the Claude Agent SDK — behind one `Backend` protocol (`src/ai_team/core/backend.py`), so an identical brief can be run through each and compared on correctness, wall-clock time, and cost. Two consequences for contributors:

- **Most changes should be backend-aware.** A guardrail, tool, or agent change that only works on one backend is usually incomplete. If a change is deliberately backend-specific, say so in the PR.
- **Comparison claims need data, not a single run.** Same-config runs vary widely (the smoke brief has ranged 6m50s → 10m41s within one hour). Any claim about a backend's speed, cost, or reliability should come from a batch of runs — see [`scripts/run_smoke_batch.py`](scripts/run_smoke_batch.py) and the n=5 note under *PR process* below.

## Development setup

### Prerequisites

- Python 3.11, 3.12 or 3.13 (`requires-python >=3.11,<3.14`; CI tests 3.11 and 3.12)
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
- ruff (format + lint), mypy
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

We use **Ruff** for formatting and linting and **mypy** for types. Ruff's formatter
replaces Black and its `I` rule replaces isort; running Black alongside it causes
formatting churn, so neither is installed.

### Ruff

- Line length: 100 (configured in `pyproject.toml`).
- Format: `uv run ruff format .`
- Lint (includes import sorting): `uv run ruff check --fix .`
- Rules: E, F, I, N, W, UP, B, C4, SIM; E501 is left to the formatter.

### mypy (type checking)

- Target: `python_version = "3.12"` in `[tool.mypy]`.
- Run: `uv run mypy src/` and `uv run mypy evals/` (both run in CI)
- Config: `warn_return_any`, `warn_unused_configs`, `ignore_missing_imports` in `pyproject.toml`.

Before opening a PR, ensure:

```bash
uv run ruff format .
uv run ruff check .
uv run mypy src/ evals/
uv run pytest
```

## PR process and commit messages

1. **Branch:** Create a feature branch from `main` (e.g. `feature/add-xyz`, `fix/issue-123`). Do not commit directly to `main`.
2. **Tests:** Add or update tests as needed; all tests must pass.
3. **Lint/format:** Run ruff and mypy as above.
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

**No API budget? Validate the harness for free.** If your change is to the batch runner, the statistics, or the verdict rendering — not to a backend's live behavior — you don't need to pay for runs. Replay a recorded bundle instead:

```bash
uv run python scripts/run_smoke_batch.py --replay example_mixed_model_n5
```

This exercises the full parse → confidence-interval → verdict pipeline at $0. See [tests/fixtures/smoke_batch/RECORD_REPLAY.md](tests/fixtures/smoke_batch/RECORD_REPLAY.md) for how to record your own fixture from a real run.

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

## Adding backends, tools, guardrails, roles, checks or specs

Step-by-step recipes, with the files to touch and the tests that catch a missed step, are in
[docs/EXTENDING.md](docs/EXTENDING.md):

- [Add a backend](docs/EXTENDING.md#add-a-backend): implement `Backend`, honour the conformance
  script, get tools from the ToolBus bridge, register it, add it to the conformance suite.
- [Add a tool](docs/EXTENDING.md#add-a-tool): register a `ToolSpec` on the ToolBus; never call
  file or shell code around it.
- [Add a guardrail](docs/EXTENDING.md#add-a-guardrail): write it once, wire it into each backend.
- [Add an agent role or a team profile](docs/EXTENDING.md#add-an-agent-role-or-a-team-profile)
- [Add a failure mode and its check](docs/EXTENDING.md#add-a-failure-mode-and-its-check)
- [Add or update a spec](docs/EXTENDING.md#add-or-update-a-spec)

Where things live: [docs/MODULE_MAP.md](docs/MODULE_MAP.md). Every env var:
[docs/CONFIGURATION.md](docs/CONFIGURATION.md).

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

When you add or change a knob, update [docs/CONFIGURATION.md](docs/CONFIGURATION.md) (the full list) and, for the common ones, the *Configuration reference* in [README.md](README.md).

If you add a new retry path, a new backend invoke, or anything that can loop over LLM
calls, make sure it stays bounded by these (or add an equivalent guard) and document it
in [docs/GUARDRAILS.md](docs/GUARDRAILS.md) → *LangGraph backend operational guardrails*.
The spend ceiling is non-retryable by design (`BudgetExceededError` subclasses
`BaseException`); do not catch it in phase nodes.

If you are unsure where a change belongs, open an issue or ask in the PR description.
