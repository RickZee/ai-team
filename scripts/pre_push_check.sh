#!/usr/bin/env bash
# Mirror CI lint + security gates before git push. Run from repo root: ./scripts/pre_push_check.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> ruff check"
uv run ruff check .

echo "==> ruff format --check"
uv run ruff format --check .

echo "==> mypy"
uv run mypy src/

echo "==> pip-audit (upgrade pip like CI security job)"
uv run python -m pip install --upgrade "pip>=26.1.2" -q
./scripts/pip_audit.sh

echo "All pre-push checks passed."
