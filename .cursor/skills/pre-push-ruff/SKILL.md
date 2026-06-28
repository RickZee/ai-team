---
name: pre-push-ruff
description: >-
  Run Ruff lint and format before git push or PR. Use when pushing code, when CI
  failed on Lint, or after editing Python files. Prefer ./scripts/pre_push_check.sh
  for the full CI gate (includes mypy and pip-audit).
---

# Pre-push Ruff (lint + format)

## When to apply

- Before **git push** or opening a PR after Python edits.
- CI **Lint** job failed on `ruff check` or `ruff format --check`.
- Quick iteration on style only (full gate: `pre-push-checks` skill → `./scripts/pre_push_check.sh`).

## Commands

From repository root:

```bash
poetry run ruff check .
poetry run ruff format --check .
```

**Auto-fix** (safe for most I001 / format issues):

```bash
poetry run ruff check . --fix
poetry run ruff format .
```

Re-run check until exit code 0.

## Notes

- CI also runs `mypy src/` — use `./scripts/pre_push_check.sh` before push.
- Cursor hook blocks `git push` when the full pre-push script fails.
