#!/usr/bin/env bash
# Run unit tests the same way .github/workflows/ci.yml does.
#
# Usage (from repo root):
#   ./scripts/ci_unit_test.sh              # no coverage (CI Test 3.11)
#   ./scripts/ci_unit_test.sh --cov        # with coverage gate (CI Test 3.12)
#   ./scripts/ci_unit_test.sh --python 3.11
#   ./scripts/ci_unit_test.sh --python 3.12 --cov
#
# Environment (optional):
#   PYTHON_VERSION=3.12   same as --python
#   CI_UNIT_VERBOSE=1     use -v instead of -q
set -euo pipefail
cd "$(dirname "$0")/.."

WITH_COV=false
PYTHON_VERSION="${PYTHON_VERSION:-}"

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cov)
      WITH_COV=true
      ;;
    --python)
      PYTHON_VERSION="${2:?--python requires a version, e.g. 3.12}"
      shift
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

mkdir -p test-results .coverage-data

PY_TAG="${PYTHON_VERSION:-${PY_TAG:-local}}"
export COVERAGE_FILE=".coverage-data/.coverage.${PY_TAG}"
export COVERAGE_CORE=sysmon

PYTEST_ARGS=(tests/unit --tb=short --junitxml=test-results/unit.xml)
if [[ "${CI_UNIT_VERBOSE:-}" == "1" ]]; then
  PYTEST_ARGS=(-v "${PYTEST_ARGS[@]}")
else
  PYTEST_ARGS=(-q "${PYTEST_ARGS[@]}")
fi

if [[ "$WITH_COV" == true ]]; then
  PYTEST_ARGS+=(--cov=src/ai_team --cov-report=xml --cov-report=term)
fi

if [[ -n "$PYTHON_VERSION" ]]; then
  uv run --python "$PYTHON_VERSION" pytest "${PYTEST_ARGS[@]}"
else
  uv run pytest "${PYTEST_ARGS[@]}"
fi
