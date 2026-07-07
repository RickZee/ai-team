#!/usr/bin/env bash
# Mirror CI gates before git push. Run from repo root: ./scripts/pre_push_check.sh
#
# Default: ruff, mypy, pip-audit, and unit tests (pytest tests/unit).
#
# Options:
#   --integration   Also run pytest tests/integration (CI: main push only)
#   --frontend      Also run npm ci && npm run build (web dashboard)
#   --e2e           Also run Playwright web E2E (implies --frontend)
#   --main          Shorthand for --integration --frontend --e2e (pushing to main)
#   --quick         Lint + security only (skip all pytest / npm)
#   -h, --help      Show usage
set -euo pipefail
cd "$(dirname "$0")/.."

RUN_UNIT=true
RUN_INTEGRATION=false
RUN_FRONTEND=false
RUN_E2E=false

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --integration)
      RUN_INTEGRATION=true
      ;;
    --frontend)
      RUN_FRONTEND=true
      ;;
    --e2e)
      RUN_E2E=true
      RUN_FRONTEND=true
      ;;
    --main)
      RUN_INTEGRATION=true
      RUN_FRONTEND=true
      RUN_E2E=true
      ;;
    --quick)
      RUN_UNIT=false
      RUN_INTEGRATION=false
      RUN_FRONTEND=false
      RUN_E2E=false
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1 (try --help)" >&2
      exit 2
      ;;
  esac
  shift
done

echo "==> ruff check"
uv run ruff check .

echo "==> ruff format --check"
uv run ruff format --check .

echo "==> mypy"
uv run mypy src/

if [[ "$RUN_UNIT" == true ]]; then
  echo "==> pytest tests/unit (CI 3.12 parity: with coverage)"
  ./scripts/ci_unit_test.sh --cov
fi

if [[ "$RUN_INTEGRATION" == true || "$RUN_FRONTEND" == true ]]; then
  echo "==> extended gates (integration and/or frontend — may take a few minutes)"
fi

if [[ "$RUN_INTEGRATION" == true ]]; then
  echo "==> pytest tests/integration"
  uv run pytest tests/integration -q --tb=short
fi

if [[ "$RUN_FRONTEND" == true ]]; then
  echo "==> frontend build (npm ci && npm run build)"
  (
    cd src/ai_team/ui/web/frontend
    npm ci --silent
    npm run build
  )
fi

if [[ "$RUN_E2E" == true ]]; then
  echo "==> playwright install chromium"
  uv run playwright install chromium
  echo "==> pytest tests/e2e/web (web_e2e)"
  uv run pytest tests/e2e/web -m web_e2e -q --tb=short --timeout=120
fi

echo "==> pip-audit (upgrade pip like CI security job)"
uv run python -m pip install --upgrade "pip>=26.1.2" -q
./scripts/pip_audit.sh

echo "All pre-push checks passed."
