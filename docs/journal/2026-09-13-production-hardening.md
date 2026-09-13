# 2026-09-13 — Production hardening Track A

Landing `.kiro/specs/production-hardening` Track A (Phases 0–5, 8–9 except
live-spend 9.1). Offline only.

## Decisions (design §12 defaults)

Wire `lessons_loop`, `qa_verdicts`, `verifiers`. Dormant: `session_loop`
(`AI_TEAM_SESSION_LOOP`), `ladder_report` (`evals.cli ladder report`). Keep
`.archive/` with a retention README (owner override of design 12.4). Container
serves the UI. Track B (package move, router split) landed in the same sitting
as Phases 6–7.

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

## Track B — 6.1 eval→core

Evals no longer import `ai_team.flows` or `ai_team.backends`. CHK-listener-self-trigger
reads `ai_team.core.flow_wiring` (CrewAI `AITeamFlow` registers at import). Solo arm
uses `ai_team.core.workspace_layout`. Deleted `flows/listener_introspection.py` after
the logic moved to core (reachability would have flagged the re-export as test-only).
Unregistered flow class does not pin an empty eval cache.

## Track B — 6.2 CrewAI package move

`git mv` of `agents/`, `crews/`, `tasks/`, `flows/` under
`src/ai_team/backends/crewai_backend/`. YAML config still lives in `ai_team.config`
(resolved via the config package path, not `parent.parent`). Lazy flow→crew imports
are relative so the >80-line ratchet stays at 58. Web E2E 27 passed, 1 skipped.

## Track B — 6.3–6.7

Deprecated shims at `ai_team.{agents,crews,tasks,flows}` warn and re-export until
2026-12-31 (v0.3.0). Import-direction guard covers core/config/harness/tools/guardrails/memory/evals
↛ backends/ui, plus backend subtrees ↛ each other. Guardrails `__init__` is a facade;
logic lives in `legacy.py`. `utils/` dissolved (`coverage_paths` → tools, `demo_input` →
config, `comparison` → backends, `callbacks`/`llm_wrapper` → crewai_backend; `reasoning.py`
deleted as unreachable). `models/outputs.py` removed; artifacts service already normalized
dicts. `models/` kept as domain types (design.md §4). README tree updated. Unit 1527,
web E2E 27 passed / 1 skipped.

## Track B — Phase 7 complexity

`_cmd_run` is a one-parameter adapter over `RunOptions` / `execute_run` (`cli_run.py`).
MCP tools are one builder per group; a frozen catalog bytes test pins the advertised
list. `evaluate_gate` is a decision table over per-criterion helpers; Tier A still
prints `verdict=fail` on the fail/pass fixture corpus. Web routes live in
`ui/web/routers/` with `create_app()` owning CORS and SPA registration. Dashboard
tokens resolve monitor → receipt/disk → live spend. Complexity ratchet 58/7/15 →
55/4/14. Web E2E 27 passed / 1 skipped.

## Phase 3 leftovers (no live spend)

Task 3.5: skip-on-parse / skip-on-empty-LLM / skip-on-missing-judge became
`pytest.fail`. Remaining skips name a precondition. Isolation: golden writes
already go to `tmp_path`; `tests/conftest.py` now also restores ToolBus and
Settings after every test. Shuffled order (`pytest-randomly` seed 42) had been
failing with `Unknown tool: read_file` because `reset_bus(empty=True)` leaked
across tests via a ContextVar. Both `pytest tests/unit -p no:randomly` and
`--randomly-seed=42` are 1534 passed.

Task 1.7 BASELINE after-state refreshed: Python LOC 46,704 → 46,049 (−655);
tracked `docs/images/` blobs 9.3 MB → 5.3 MB (−4.0 MB). Box left open: GitHub
CI has not run (workflow is `main`/`develop` + PRs into those; `gh` is not
logged in).

Task 3.6: SHA-pinned `uses:`, PR/issue templates, CODEOWNERS, CHANGELOG, git
tag `v0.2.0` on origin. Box left open: `gh release list` needs GitHub Release
UI, which needs `gh auth login`.

Task 9.1 left open (human-triggered spend).

