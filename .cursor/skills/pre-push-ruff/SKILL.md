---
name: pre-push-ruff
description: >-
  Runs Ruff lint on the repository before git push or when the user asks to
  push, commit for CI, or prepare a PR. Use when pushing code, before opening a
  pull request, or when the user mentions pre-push checks, ruff, or lint CI
  failures.
---

# Pre-push Ruff

## When to apply

- The user asks to **push**, **commit and push**, **open a PR**, or **prepare for CI**.
- The conversation implies code is ready to leave the machine (merge, ship, etc.).
- CI failed on **ruff** and the user is fixing it.

## Required step

From the **repository root**, run:

```bash
poetry run ruff check .
```

- **If it fails**: fix reported issues (or run `poetry run ruff check . --fix` for auto-fixable rules), then re-run until **exit code 0**.
- **Do not** tell the user to push while Ruff still fails unless they explicitly override.

## Project defaults

- This repo uses **Poetry**; prefer `poetry run ruff check .` over a bare `ruff` that might hit the wrong environment.
- Ruff config lives in the repo (e.g. `pyproject.toml`); do not disable rules locally unless the user asks.

## Optional (not required by this skill)

If the user wants a fuller pre-push gate, suggest separate runs from project docs (e.g. mypy, pytest, `black --check`) only when they ask or workspace rules require it.
