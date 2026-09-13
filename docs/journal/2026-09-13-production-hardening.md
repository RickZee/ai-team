# 2026-09-13 — Production hardening Track A

Landing `.kiro/specs/production-hardening` Track A (Phases 0–5, 8–9 except
live-spend 9.1). Offline only.

## Decisions (design §12 defaults)

Wire `lessons_loop`, `qa_verdicts`, `verifiers`. Dormant: `session_loop`
(`AI_TEAM_SESSION_LOOP`), `ladder_report` (`evals.cli ladder report`). Keep
`.archive/` with a retention README (owner override of design 12.4). Container
serves the UI. Track B (package move, router split) deferred and recorded in
`ARCHITECTURE.md`.

## Failures found while making the gate green

- `uv build` (hatchling) packaged `frontend/node_modules` until sdist/wheel excludes were added.
- `mypy` on `smoke_tools` / `test_tools` after dropping `ignore_errors`: Pydantic `Field(False)` is not a typed default without the plugin. Switched optional fields to Python defaults.
- Session-loop unit tests called `run_sessions` without `AI_TEAM_SESSION_LOOP=1` after the dormant-flag change.
- Reachability flagged `__main__.py`, `evals/run_evals.py`, and `utils/backend_comparison.py` (the last is imported from `scripts/`).
- Reference guard hit journal relative links and a fenced-code false positive in `.kiro/specs/eval-harness/design.md`.
- Collection guard saw leftover local `.archive/compare-debug/` test files; skip `.archive`.
- Tier A baseline covered 13/20 checks; refreshed from `evals.cli run --tier A --warn-only` with a fail/pass-fixture `reason`.
- WebSocket Origin allowlist was only ports 5173/8421, so E2E on an ephemeral loopback port hung on "Connecting to live run…". Loopback Origin (any port) is now allowed; `https://evil.example` still fails.
- Docker `uv sync` failed: hatchling required `README.md` and the builder stage did not copy it.
- `docker compose … build` interpolated `AI_TEAM_WEB_TOKEN:?…` at parse time; switched to `${AI_TEAM_WEB_TOKEN:-}` so build works, bind guard still refuses `0.0.0.0` when empty.
