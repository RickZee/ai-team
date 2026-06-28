---
name: fix-ci
description: >-
  Diagnose and fix ai-team GitHub Actions CI failures (lint, test, web-e2e,
  integration, security). Use when CI is red, the user links an actions run,
  or before pushing web dashboard / E2E changes.
---

# Fix CI (ai-team)

Mirror `.github/workflows/ci.yml`. Run from **repository root** with `uv run …` locally and in CI.

For **pip-audit / bandit** only, use the `pre-push-checks` skill (`.cursor/skills/pre-push-checks/`).

## 1. Identify the failing job

| GitHub job | Local reproduction |
|------------|-------------------|
| **Lint** | `uv run ruff check .` → `uv run ruff format --check .` → `uv run mypy src/` |
| **Test** | `uv run pytest tests/unit -v --tb=short` |
| **Web UI E2E** | See [Web UI E2E](#web-ui-e2e) below |
| **Integration test** (main push only) | `uv run pytest tests/integration -v --tb=short` |
| **Security** | `./scripts/pre_push_check.sh` (or `./scripts/pip_audit.sh` only) |

With `gh` authenticated:

```bash
gh run view <run-id> --repo RickZee/ai-team --log-failed
gh run view <run-id> --job <job-id> --log-failed
```

Example run: [26157760272](https://github.com/RickZee/ai-team/actions/runs/26157760272) — **Lint** (ruff format) + **Web UI E2E** failed; unit/integration/security passed.

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

### Common Web UI E2E failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Would reformat: tests/e2e/web/...` | Lint, not E2E | `uv run ruff format tests/e2e/web/` |
| `Frontend build did not produce .../index.html` | `npm` build failed | `cd src/ai_team/ui/web/frontend && npm ci && npm run build` |
| `playwright` / browser missing | Chromium not installed | `uv run playwright install chromium` |
| `dashboard-active` / `COMPLETE` timeout | Demo slow or UI drift on Linux CI | Confirm `data-testid` on `src/ai_team/ui/web/frontend/src/pages/Run.tsx`, `Dashboard.tsx`, `PhasePipeline.tsx`; demo ~30–60s — tests use 90s; check `src/ai_team/ui/web/server.py` `_run_demo_async` |
| `get_by_test_id(...)` not found | React `data-testid` ≠ Python selector | Grep `data-testid` in `frontend/src` and align `tests/e2e/web/test_browser_e2e.py` |
| `get_by_text("CrewAI")` etc. | Copy/layout change on Compare/Run | Update test or restore visible labels |
| API demo timeout | `/api/demo` never reaches `complete` | Run `test_demo_run_reaches_complete_via_rest` alone; inspect `GET /api/runs/{id}` |

**UI change checklist** (before push):

1. `uv run ruff format --check .`
2. `npm run build` in `src/ai_team/ui/web/frontend`
3. Full `pytest tests/e2e/web -m web_e2e` (or at least touched test file)

Docs: `tests/e2e/web/README.md`

## 4. Test job

```bash
uv run pytest tests/unit -v --tb=short --cov=src/ai_team --cov-report=term
```

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
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run pytest tests/unit -q
uv run pytest tests/e2e/web -m web_e2e -q --timeout=120
```

Optional if touching dependencies: `./scripts/pip_audit.sh` (included in `./scripts/pre_push_check.sh`).

## 8. Node.js 20 deprecation warnings

CI annotations about Node 20 on Actions runners are **warnings** from `actions/*@v4`/`v5`; they did not fail run 26157760272. Ignore unless upgrading workflow actions.
