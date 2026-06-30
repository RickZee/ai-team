---
name: pre-push-checks
description: >-
  Runs Ruff, mypy, unit tests, and pip-audit before git push or when preparing
  for CI/PR. Use --main, --frontend, or --e2e for fuller gates. Use when pushing
  code, opening a pull request, or when CI failed on ruff, tests, pip-audit, or
  security.
---

# Pre-push checks

## When to apply

- The user asks to **push**, **commit and push**, **open a PR**, or **prepare for CI**.
- The conversation implies code is ready to leave the machine (merge, ship, etc.).
- CI failed on **ruff**, **tests**, **pip-audit**, **security**, or **web build**.

## Required steps

From the **repository root**, run the shared script (mirrors CI):

```bash
./scripts/pre_push_check.sh
```

Default gate: **ruff** + **mypy** + **unit tests** + **pip-audit**.

| Flag | Adds |
|------|------|
| `--main` | `pytest tests/integration` + `npm run build` (use before pushing **main**) |
| `--frontend` | `npm ci && npm run build` in `src/ai_team/ui/web/frontend` |
| `--integration` | `pytest tests/integration` |
| `--e2e` | frontend build + Playwright Chromium + `pytest tests/e2e/web -m web_e2e` |
| `--quick` | lint + security only (skip pytest / npm) |

Examples:

```bash
./scripts/pre_push_check.sh              # everyday push (feature branches)
./scripts/pre_push_check.sh --main       # push to main (integration + TS build)
./scripts/pre_push_check.sh --e2e        # after web UI changes
./scripts/pre_push_check.sh --quick      # lint-only iteration
```

- **If it fails**: fix issues, then re-run until **exit code 0**.
- Do **not** hand-roll pip-audit flags; use `./scripts/pip_audit.sh` (same ignores as `ci.yml`).

### Manual breakdown (if iterating on one gate)

```bash
uv run ruff check .
uv run ruff format --check .   # or: uv run ruff format .
uv run mypy src/
uv run pytest tests/unit -q --tb=short
uv run pytest tests/integration -q --tb=short   # main push
cd src/ai_team/ui/web/frontend && npm ci && npm run build
uv run python -m pip install --upgrade "pip>=26.1.2"
./scripts/pip_audit.sh
```

## Project defaults

- Use **`uv run …`** so tools use the project virtualenv.
- **`pip-audit`** is a project dev dependency; do not assume a global install.
- A **Cursor hook** (`.cursor/hooks.json`) blocks `git push` when `./scripts/pre_push_check.sh` fails.
  On branch **`main`**, the hook automatically passes **`--main`**.
- Optional **pre-commit**: `uv run pre-commit install` (ruff + ruff-format on commit).

## Optional (heavier gates)

- **`--e2e`**: full Playwright suite — run when changing dashboard UX or E2E tests.
- **bandit**: CI security job only; not in pre-push script.
