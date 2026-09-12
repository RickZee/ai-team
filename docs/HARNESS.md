# Seven-layer production harness

The product is the **shared harness**. CrewAI, LangGraph, and the Claude Agent
SDK are engines. This document is the instrumentation bar: every layer lists
the module that owns it, the failure modes it covers, the eval checks, and
whether it is instrumented, enforced, or closed-loop.

See [ARCHITECTURE.md](ARCHITECTURE.md) for crews, agents, and backends.
See [evals/taxonomy/COVERAGE.md](../evals/taxonomy/COVERAGE.md) for FM coverage.

## Status table (R19.3)

| Layer | Post requirement | Module | FM ids | Checks | Status |
| --- | --- | --- | --- | --- | --- |
| Tools | Structured observations; draft-then-commit; irreversible gated | `src/ai_team/tools/bus.py`, `kinds.py`, `draft.py`, `catalog.py` | FM-001, FM-012 | CHK-tool-call-emitted, CHK-draft-commit | **enforced** |
| Verification | Cheap (pytest/ruff/smoke) vs strong (judge); smoke on every backend | `src/ai_team/harness/verifiers.py`, `tools/smoke_tools.py`, CrewAI `on_run_smoke` | FM-006, FM-010 | CHK-runtime-smoke-present, CHK-gate-env-fidelity | **enforced** |
| Context | Pinned `docs/CONSTRAINTS.md`; `STATE.md` last-N facts; no summarizer rewrite | `src/ai_team/harness/context.py` | FM-011 | CHK-constraint-survival | **enforced** |
| Guardrails | `risk_class` subsets; spend ceiling stays global | `src/ai_team/harness/guardrail_risk.py`, `guardrails/` | FM-005, FM-007 | CHK-guardrail-fp-budget, CHK-spend-ceiling | **enforced** |
| Observability | Disk change receipt is source of truth; dashboard reads the file | `src/ai_team/harness/receipt.py`, `GET /api/runs/{id}/receipt` | FM-003, FM-004, FM-008 | CHK-interrupt-latency, CHK-workspace-isolation, CHK-metric-source-agreement | **enforced** (dashboard cost/smoke/files prefer `receipt.json`; live WS is projection-only) |
| Routing | `task_routes.yaml`; `mechanical_check` → `deterministic` | `src/ai_team/harness/router.py`, `config/task_routes.yaml` | — | cheap path unit tests | **instrumented** |
| Feedback | Structured lessons → pin `CST-lesson-*`; effectiveness window | `src/ai_team/harness/lessons_loop.py` | FM-013 | CHK-lesson-effectiveness | **closed-loop** |

**Status meanings**

- **instrumented** — spans, files, or metrics exist; a backend can still skip them.
- **enforced** — the default path cannot complete a write/verify/pin without the layer.
- **closed-loop** — a failure writes a lesson that is loaded on the next run and can be marked effective / ineffective / escalated.

Honest gaps: CrewAI and Claude SDK inject `CONSTRAINTS.md` when the file has items;
LangGraph always prepends via `build_system_prompt`. Native SDK `Write`/`Bash` are
denied only when `AI_TEAM_DENY_NATIVE_TOOLS` is set. Cheap vs strong routing is
wired for verifiers; role models still come from `config/models.py` until every
call site uses `resolve_route`.

## ToolBus

All file/code write, delete, and shell entrypoints go through
`ToolBus.invoke({tool, args}) → ToolObservation`. Process-local via
`get_bus()` / `reset_bus()` (`ContextVar`, not a cross-run singleton).

Writes stage under `workspace/.harness/drafts/` until `commit_write`.
Default `AI_TEAM_DRAFT_WRITES=1`. Tests not yet on draft use `AI_TEAM_DRAFT_WRITES=0`.
Irreversible tools (`delete_file`, `execute_shell`, lockfile overwrite) require
`allow_irreversible` / human token / `AI_TEAM_ALLOW_IRREVERSIBLE=1`. Model
`confirm=true` is not enough.

## Three-file contract

| File | Owner | Rule |
| --- | --- | --- |
| `docs/CONSTRAINTS.md` | harness | Never summarized. Injected as a pinned prompt block. |
| `docs/STATE.md` | harness | Last N phase facts (JSON fence). No LLM. |
| `docs/LESSONS.md` | harness | Rendered from the lesson store. |

Compaction policy: `ConstraintLoader.pinned_text()` is untouchable. The dummy
summarizer in `harness/context.py` drops other context and keeps the pin.

## Change receipt

`output/runs/<id>/receipt.json` + `receipt.md` written at finalize. The live
event stream is not the source of truth for cost, files, or smoke.
`cost_per_accepted_change = total_usd / max(accepted_changes, 1)`.
Week-over-week: `python -m evals.cli drift --current DIR --previous DIR` (warn-only, $0).

The web dashboard (`GET /api/runs/{id}`, Compare monitor serialization) prefers
receipt fields for cost and smoke once the file exists. WebSocket events remain
a live projection for progress UX only.

## Run journal (reconstruct, not rewind)

`workspace/<id>/logs/journal.jsonl` is an append-only stream of ToolBus
allow/deny events with `backend`, `phase`, `tool`, `decision`, optional
`spend_delta_usd`, and `constraint_pin_hash`. It supports post-hoc inspection
alongside `audit.jsonl` / `phases.jsonl`.

**Not a session DOM:** rewind, fork, and interactive resume from the journal are
out of scope. Durable replay for CI is eval fixture traces + the change receipt
(see [EVALS.md](EVALS.md)), not journal replay.

## Env flags

| Variable | Default | Meaning |
| --- | --- | --- |
| `AI_TEAM_DRAFT_WRITES` | on | Stage writes before commit |
| `AI_TEAM_ALLOW_IRREVERSIBLE` | off | Permit delete/shell/lockfile |
| `AI_TEAM_DENY_NATIVE_TOOLS` | off | SDK PreToolUse denies native Write/Bash |
| `AI_TEAM_CONSTRAINT_CANARY` | unset | Seed `CST-canary` at run start |
