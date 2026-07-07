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
- CI failed on **ruff**, **tests**, **pip-audit**, **security**, **web build**, or **web E2E**.

For **diagnosing a red GitHub Actions run** after push, also read `fix-ci` (`.cursor/skills/fix-ci/`).

## Required steps

From the **repository root**, run the shared script (mirrors CI):

```bash
./scripts/pre_push_check.sh
```

Default gate: **ruff** + **mypy** + **unit tests with coverage** (`ci_unit_test.sh --cov`) + **pip-audit**.

**Full CI parity** (both Python versions + security, no E2E):

```bash
./scripts/ci_check.sh --matrix
```

| Flag | Adds | CI jobs it helps catch |
|------|------|------------------------|
| `--main` | integration + `npm run build` + Playwright E2E | **Integration test**, **Web UI E2E**, plus all default gates |
| `--frontend` | `npm ci && npm run build` | TS compile errors (part of **Web UI E2E**) |
| `--integration` | `pytest tests/integration` | **Integration test** (main push only in CI) |
| `--e2e` | frontend build + Chromium + `pytest tests/e2e/web -m web_e2e` | **Web UI E2E** |
| `--quick` | lint + security only (skip pytest / npm) | **Lint** + **Security** only |

Examples:

```bash
./scripts/pre_push_check.sh              # everyday push (feature branches)
./scripts/pre_push_check.sh --main       # push to main — use this before merging to main
./scripts/pre_push_check.sh --e2e        # after web UI / Playwright test changes
./scripts/pre_push_check.sh --quick      # lint-only iteration
```

- **If it fails**: fix issues, then re-run until **exit code 0**.
- Do **not** hand-roll pip-audit flags; use `./scripts/pip_audit.sh` (same ignores as `ci.yml`).

### Gaps that burned us (avoid repeating)

| Mistake | What CI caught | Pre-push fix |
|---------|----------------|--------------|
| Pushed to **main** with default script only | **Web UI E2E** (stale `dashboard-active` selectors) | Use `--main` or `--e2e` after dashboard changes; hook on `main` passes `--main` automatically |
| Unit tests pass locally, **Test** job red with 0 junit failures | Coverage `fail_under` on `ubuntu-latest` (branch coverage) | `./scripts/ci_unit_test.sh --cov`; for both legs: `./scripts/ci_check.sh --matrix` |
| **Test (3.11)** red, junit shows 0 failures | Upload step tried `coverage.xml` without `--cov` | Fixed in CI (`if: matrix.python-version == '3.12'`); see `fix-ci` §0 step map |
| `test_run_demo.py` calls `run_demo.main()` | **SIGALRM** / signal clashes on Linux CI | Tests must mock `_install_timeout` → `False`; see `tests/unit/test_run_demo.py` |

### Manual breakdown (if iterating on one gate)

```bash
uv run ruff check .
uv run ruff format --check .   # or: uv run ruff format .
uv run mypy src/
uv run pytest tests/unit -q --tb=short --cov=src/ai_team   # or: ./scripts/ci_unit_test.sh --cov
uv run pytest tests/integration -q --tb=short   # main push
cd src/ai_team/ui/web/frontend && npm ci && npm run build
uv run playwright install chromium
uv run pytest tests/e2e/web -m web_e2e -q --tb=short --timeout=120
uv run python -m pip install --upgrade "pip>=26.1.2"
./scripts/pip_audit.sh
```

## Project defaults

- Use **`uv run …`** so tools use the project virtualenv.
- **`pip-audit`** is a project dev dependency; do not assume a global install.
- A **Cursor hook** (`.cursor/hooks.json`) blocks `git push` when `./scripts/pre_push_check.sh` fails.
  On branch **`main`**, the hook automatically passes **`--main`** (integration, frontend build, and web E2E).
- Optional **pre-commit**: `uv run pre-commit install` (ruff + ruff-format on commit).

## CI vs pre-push (quick map)

| CI job | Pre-push equivalent |
|--------|---------------------|
| Lint | default (ruff + mypy) |
| Test (3.11) | `./scripts/ci_unit_test.sh --python 3.11` or `ci_check.sh --matrix` |
| Test (3.12) | default (`ci_unit_test.sh --cov` via `pre_push_check.sh`) |
| Web UI E2E | `--e2e` or `--main` |
| Integration test | `--integration` or `--main` |
| Security | default (pip-audit); bandit is CI-only |

## Optional (heavier gates)

- **`--e2e`**: full Playwright suite — **required** when changing Home/RunDetail UX, `data-testid`s, or `tests/e2e/web/`.
- **bandit**: CI security job only; not in pre-push script.
