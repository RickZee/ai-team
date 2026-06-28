---
name: pre-push-checks
description: >-
  Runs Ruff, mypy, and pip-audit before git push or when preparing for CI/PR.
  Use when pushing code, opening a pull request, or when CI failed on ruff,
  pip-audit, or security.
---

# Pre-push checks (Ruff + mypy + pip-audit)

## When to apply

- The user asks to **push**, **commit and push**, **open a PR**, or **prepare for CI**.
- The conversation implies code is ready to leave the machine (merge, ship, etc.).
- CI failed on **ruff**, **pip-audit**, or **security** job.

## Required steps

From the **repository root**, run the shared script (mirrors CI lint + security jobs):

```bash
./scripts/pre_push_check.sh
```

- **If it fails**: fix issues, then re-run until **exit code 0**.
- Do **not** hand-roll pip-audit flags; use `./scripts/pip_audit.sh` (same ignores as `ci.yml`).

### Manual breakdown (if iterating on one gate)

```bash
uv run ruff check .
uv run ruff format --check .   # or: uv run ruff format .
uv run mypy src/
uv run python -m pip install --upgrade "pip>=26.1.2"
./scripts/pip_audit.sh
```

## Project defaults

- Use **`uv run …`** so tools use the project virtualenv.
- **`pip-audit`** is a project dev dependency; do not assume a global install.
- A **Cursor hook** (`.cursor/hooks.json`) blocks `git push` when `./scripts/pre_push_check.sh` fails.
- Optional **pre-commit**: `uv run pre-commit install` (ruff + ruff-format on commit).

## Optional (not required by this skill)

pytest, bandit — run when the user asks or the `fix-ci` skill applies.
