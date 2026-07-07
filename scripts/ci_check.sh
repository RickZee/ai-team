#!/usr/bin/env bash
# Systematic local mirror of .github/workflows/ci.yml.
#
# Usage (from repo root):
#   ./scripts/ci_check.sh              # lint + unit (cov) + security
#   ./scripts/ci_check.sh --matrix     # also run unit tests on 3.11 (no cov)
#   ./scripts/ci_check.sh --main       # full main-branch push parity
#   ./scripts/ci_check.sh --quick      # lint + security only
#   ./scripts/ci_check.sh --help
set -euo pipefail
cd "$(dirname "$0")/.."

RUN_MATRIX=false
MAIN=false
QUICK=false

usage() {
  sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --matrix)
      RUN_MATRIX=true
      ;;
    --main)
      MAIN=true
      ;;
    --quick)
      QUICK=true
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

if [[ "$MAIN" == true ]]; then
  exec ./scripts/pre_push_check.sh --main
fi

if [[ "$QUICK" == true ]]; then
  exec ./scripts/pre_push_check.sh --quick
fi

echo "==> CI parity: Lint (ruff + mypy)"
uv run ruff check .
uv run ruff format --check .
uv run mypy src/

echo "==> CI parity: Test (3.12 with coverage)"
./scripts/ci_unit_test.sh --python 3.12 --cov

if [[ "$RUN_MATRIX" == true ]]; then
  echo "==> CI parity: Test (3.11 without coverage)"
  ./scripts/ci_unit_test.sh --python 3.11
fi

echo "==> CI parity: Security (pip-audit)"
uv run python -m pip install --upgrade "pip>=26.1.2" -q
./scripts/pip_audit.sh

echo "All ci_check gates passed."
