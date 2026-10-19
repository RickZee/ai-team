# 2026-10-19 — mcp and claude-agent-sdk floors for pip-audit

**`./scripts/pre_push_check.sh` failed at its last step, pip-audit.** Ruff, mypy and the unit tests passed. The locked `mcp` 1.28.1 had CVE-2026-59951 (fixed in 1.30.0 / 2.2.0). `uv tree --invert --package mcp` shows two dependents, `claude-agent-sdk` 0.2.110 and `crewai` 1.6.1. Neither is ours to change, so the floor went into `[tool.uv] constraint-dependencies` next to the 2026-10-07 entries ([pip-audit floors](2026-10-07-pip-audit-floors.md)). `uv lock --upgrade-package mcp` moved only `mcp`, to 1.30.0, and stayed on the 1.x line that CrewAI 1.6 resolves with.

**The rerun found a second advisory that the mcp finding had hidden:** `claude-agent-sdk` 0.2.110 has CVE-2026-96620, fixed in 0.2.121. `claude-agent-sdk` is a direct dependency, so its floor in `[project] dependencies` went from `>=0.1.0` to `>=0.2.121`. `uv lock --upgrade-package claude-agent-sdk` resolved to 0.2.168, the newest release, and kept `mcp` at 1.30.0.

**Verified:** `uv run pytest tests/unit/backends tests/conformance -q` gave 357 passed on the new SDK. In `./scripts/pre_push_check.sh`, the unit suite gave 1785 passed and pip-audit reported "No known vulnerabilities found, 38 ignored". The ignore list did not change. There was no live Claude Agent SDK run; only mocked backend tests ran.
