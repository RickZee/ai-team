---
name: fix-ci
description: >-
  Diagnose and fix ai-team GitHub Actions CI failures (lint, test, web-e2e,
  integration, security). Use when CI is red, the user links an actions run,
  or before pushing web dashboard / E2E changes.
---

# Fix CI (ai-team)

Mirror `.github/workflows/ci.yml`. Run from **repository root** with `uv run …` locally and in CI.

**Single source of truth for unit tests:** `./scripts/ci_unit_test.sh` (used by CI, `pre_push_check.sh`, and `ci_check.sh`).

For **local pre-push gates**, use the `pre-push-checks` skill (`.cursor/skills/pre-push-checks/`).
For **pip-audit / bandit** only, same skill.

## 0. Systematic triage (start here)

1. Open the [failed run](https://github.com/RickZee/ai-team/actions) → note **which job** is red (ignore **cancelled** matrix legs).
2. Map the job to a local command (table in §1).
3. Reproduce locally. Prefer `./scripts/ci_check.sh --matrix` before push to main (lint + 3.12 cov + 3.11 + security).
4. Fix root cause — do not lower coverage threshold or skip tests without evidence.
5. Re-run the narrowest repro, then `./scripts/pre_push_check.sh --main` if pushing to `main`.

### Test job step map (`ci.yml`)

| Step name | 3.11 | 3.12 | Common failure |
|-----------|------|------|----------------|
| Run unit tests | no `--cov` | `--cov` + `fail_under` | Real test failure; coverage below threshold |
| Upload coverage artifact | **skipped** | uploads `coverage.xml` | Was: missing `coverage.xml` on 3.11 (fixed with `if: matrix.python-version == '3.12'`) |
| Upload test results | `if: always()` | same | JUnit artifact even when an earlier step failed |

When **917 passed** but job exit **1**: if the failing step is **Upload coverage artifact** on 3.11, the matrix leg ran pytest without `--cov` — conditional upload fixes it. If the failing step is **Run unit tests** on 3.12, it is almost always `fail_under`.

Recent examples:

- [28860833088](https://github.com/RickZee/ai-team/actions/runs/28860833088) — **Test** + **Web UI E2E** (stale Playwright selectors after Home/RunDetail IA).
- [28894155070](https://github.com/RickZee/ai-team/actions/runs/28894155070) — **Test (3.12)** only; **917 passed, exit 1** = coverage `fail_under` on `ubuntu-latest`.
- [28896523194](https://github.com/RickZee/ai-team/actions/runs/28896523194) — **Test (3.11)**; pytest green but **Upload coverage artifact** failed (no `coverage.xml` on non-cov leg).

Matrix note: `fail-fast: false` — both Python versions finish; fix the leg that actually failed, not a **cancelled** sibling from old concurrency.

## 1. Identify the failing job

| GitHub job | Local reproduction |
|------------|-------------------|
| **Lint** | `uv run ruff check .` → `uv run ruff format --check .` → `uv run mypy src/` |
| **Test (3.11)** | `./scripts/ci_unit_test.sh --python 3.11` |
| **Test (3.12)** | `./scripts/ci_unit_test.sh --python 3.12 --cov` |
| **Both Test legs** | `./scripts/ci_check.sh --matrix` |
| **Web UI E2E** | See [Web UI E2E](#web-ui-e2e) below |
| **Integration test** (main push only) | `uv run pytest tests/integration -v --tb=short` |
| **Security** | `./scripts/pip_audit.sh` (after `pip install --upgrade "pip>=26.1.2"`) |

With `gh` authenticated:

```bash
gh run view <run-id> --repo RickZee/ai-team --log-failed
gh run view <run-id> --job <job-id> --log-failed
```

## 2. Lint job

Run in order; stop at first failure and fix before continuing:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
```

**Fix ruff format** (safe auto-fix):

```bash
uv run ruff format .
# or one file:
uv run ruff format tests/e2e/web/test_browser_e2e.py
```

Re-run `uv run ruff format --check .` until exit code 0.

**Fix ruff check**: `uv run ruff check . --fix` where safe; hand-fix the rest.

**Fix mypy**: type hints / `cast` / narrow unions in `src/ai_team/` only (CI runs `mypy src/`).

## 3. Web UI E2E

Matches CI `web-e2e` job:

```bash
uv sync
uv run playwright install chromium
cd src/ai_team/ui/web/frontend && npm ci && npm run build
cd -  # repo root
uv run pytest tests/e2e/web -m web_e2e -v --tb=short --timeout=120
```

Faster subsets while iterating:

```bash
# API only (no Playwright browser)
uv run pytest tests/e2e/web/test_api_e2e.py -m web_e2e -v --timeout=120

# Browser only
uv run pytest tests/e2e/web/test_browser_e2e.py -m web_e2e -v --timeout=120
```

Skip frontend build (browser tests skipped):

```bash
AI_TEAM_SKIP_FRONTEND_BUILD=1 uv run pytest tests/e2e/web -m web_e2e -v
```

### IA-1 selector map (Dashboard → Home + RunDetail)

After the UI restructure, **do not** use old Dashboard test ids. Grep `data-testid` in
`src/ai_team/ui/web/frontend/src` and align `tests/e2e/web/test_browser_e2e.py`.

| Stale (pre-IA-1) | Current |
|------------------|---------|
| `nav-dashboard` | `nav-home` |
| `nav-run` (navbar) | `home-new-run` (Home page CTA → `/run`) |
| `nav-artifacts` | removed from nav; artifacts on RunDetail tabs |
| `dashboard-active` | `run-detail` |
| `dashboard-empty` | `home-empty` |
| `dashboard-demo` | `home-demo` |
| `AI-Team Dashboard` heading | `Runs` heading on `home-page` |
| `.run-list-assignment` | `.run-list-description` |
| Demo lands on `/` dashboard | Demo lands on `/runs/{id}` (RunDetail) |

Agent activity is on the **Activity** tab: click `run-tab-activity` before asserting
`Agent timeline` / `Activity Log`.

### Common Web UI E2E failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Would reformat: tests/e2e/web/...` | Lint, not E2E | `uv run ruff format tests/e2e/web/` |
| `Frontend build did not produce .../index.html` | `npm` build failed | `cd src/ai_team/ui/web/frontend && npm ci && npm run build` |
| `playwright` / browser missing | Chromium not installed | `uv run playwright install chromium` |
| `get_by_test_id("dashboard-active")` not found | Stale selectors | See [IA-1 selector map](#ia-1-selector-map-dashboard--home--rundetail) |
| `run-detail` / `COMPLETE` timeout | Demo slow on Linux CI | Demo ~30–60s; tests allow 90s; check `_run_demo_async` in `server.py` |
| `get_by_test_id(...)` not found | React `data-testid` ≠ Python selector | Grep `data-testid` in `frontend/src` |
| `get_by_text("CrewAI")` etc. | Copy/layout change on Compare/Run | Update test or restore visible labels |
| API demo timeout | `/api/demo` never reaches `complete` | Run `test_demo_run_reaches_complete_via_rest` alone |

**UI change checklist** (before push):

1. `uv run ruff format --check .`
2. `npm run build` in `src/ai_team/ui/web/frontend`
3. `./scripts/pre_push_check.sh --e2e` (or `--main` on `main`)

Docs: `tests/e2e/web/README.md`

## 4. Test job

CI uses inline `uv run pytest` in `ci.yml` (canonical). Local mirror: `./scripts/ci_unit_test.sh` / `./scripts/ci_check.sh --matrix`.

- **Python 3.11**: unit tests only (no `--cov`).
- **Python 3.12**: unit tests **with** `--cov` + `COVERAGE_CORE=sysmon` + `fail_under` from `pyproject.toml` (currently **55**).

Local reproduction:

```bash
./scripts/ci_unit_test.sh --python 3.12 --cov
./scripts/ci_check.sh --matrix   # both Python versions
```

### Common Test job failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| **917 passed**, job exit **1**, junit **0 failures** | Coverage `fail_under` on Linux (3.12) or missing `coverage.xml` upload (3.11) | See §0 step map; run `./scripts/ci_unit_test.sh --cov` |
| `tests/unit/test_run_demo.py` fails on Linux only | `run_demo.main()` arms **SIGALRM** | Mock `_install_timeout` to return `False`; load script via `importlib` with a **unique module name** (see existing tests) |
| `demos/02_todo_app` not found | Archived demo path in tests | Use `demos/02_todo_app` (tracked) or `tmp_path` for txt fixtures; never `demos/01_hello_world` (archived) |
| `OpenAIError: Missing credentials` on Linux CI only | `compile_planning_subgraph` eagerly built manager LLM for single-worker mode | Lazy-init manager LLM in supervisor branch only (see `planning.py`); reproduce with `env -u OPENAI_API_KEY` in fresh Linux clone |

If only one area changed, run the narrowest `tests/unit/...` path first, then full unit suite.

## 5. Integration test (main only)

Runs on **push to main**, not on every PR branch. Same command as CI:

```bash
uv run pytest tests/integration -v --tb=short
```

## 6. Security job

```bash
uv run python -m pip install --upgrade "pip>=26.1.2"
./scripts/pip_audit.sh
```

Same ignore list as `.github/workflows/ci.yml` (single source: `scripts/pip_audit.sh`). For the full local gate, use `./scripts/pre_push_check.sh`.

## 7. Exit criteria

Before declaring CI fixed locally:

```bash
./scripts/ci_check.sh --matrix   # lint + both Python test legs + security
./scripts/pre_push_check.sh --main
```

`--main` = lint + mypy + unit tests (with coverage) + integration + frontend build + web E2E + pip-audit — closest match to a **main** branch CI push.

## 8. Node.js 20 deprecation warnings

CI annotations about Node 20 on Actions runners are **warnings** from `actions/*@v4`/`v5`; they do not fail the job. Ignore unless upgrading workflow actions.
