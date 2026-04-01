---
name: pre-push-checks
description: >-
  Runs Ruff and pip-audit before git push or when preparing for CI/PR. Use when
  pushing code, opening a pull request, or when CI failed on ruff, pip-audit, or
  dependency vulnerabilities.
---

# Pre-push checks (Ruff + pip-audit)

## When to apply

- The user asks to **push**, **commit and push**, **open a PR**, or **prepare for CI**.
- The conversation implies code is ready to leave the machine (merge, ship, etc.).
- CI failed on **ruff**, **pip-audit**, or **security** job.

## Required steps

From the **repository root**, run in order:

### 1. Ruff

```bash
poetry run ruff check .
```

- **If it fails**: fix issues (or `poetry run ruff check . --fix` where safe), then re-run until **exit code 0**.

### 2. pip-audit (match CI)

Use the same ignore list as the **security** job in `.github/workflows/ci.yml`:

```bash
poetry run pip-audit \
  --ignore-vuln CVE-2025-69872 \
  --ignore-vuln PYSEC-2022-42969
```

- **If it fails**: upgrade or pin vulnerable packages in `pyproject.toml` / `poetry.lock` (then `poetry lock` / `poetry update <pkg>` as appropriate), re-run until **exit code 0**.
- **Skip line for `ai-team`**: pip-audit reports *Dependency not found on PyPI* for the local editable package; that is informational and does **not** fail the audit when there are no CVEs.

## Project defaults

- Use **`poetry run …`** so tools use the project virtualenv.
- **`pip-audit`** is a Poetry **dev** dependency; do not assume a global install.

## Optional (not required by this skill)

Mypy, pytest, `black --check`, or **bandit** — run only when the user asks or workspace rules require them.
