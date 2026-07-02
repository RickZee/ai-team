# Showcase Plan — task list with acceptance criteria

Goal: make this repo the strongest possible evidence that Rick can **design, run, and
integrate complex agentic systems**. A reviewer gives it 15 minutes; in that window they
must hit: crisp thesis → one wow demo → data-backed comparison → systems maturity
(guardrails, cost control, self-healing, evals).

Strategy: five steps, each leaves the repo demoable. Get the data while everything still
runs (steps 1-2), **then** cut (step 3), then polish the surface (steps 4-5).

Source analysis: see the 2026-07-01/02 session review (CrewAI flow-wiring root cause,
spend-guard contamination, zero-metrics dashboard, kill/merge/keep table).

---

## Step 1 — Fix the CrewAI flow-wiring bug, re-run the 3-way comparison

The root cause behind three handoffs of "CrewAI deadlocks": in CrewAI Flows, a completed
method emits its **own method name** as the next trigger, so
`@listen("retry_development") def retry_development` re-triggers itself forever
(live-observed: 93,284 iterations in 15 min). Its return values
(`"run_development"` / `"escalate_to_human"`) route nowhere — plain `@listen` returns are
discarded; only `@router` returns route. The retry cap has never functioned.

### Tasks

- [ ] 1.1 Audit `flows/main_flow.py` for every `@listen("X") def X` self-trigger
      (known: `retry_development`, `retry_planning`; check `handle_fatal_error`,
      `escalate_to_human`, all `handle_*_error`).
- [ ] 1.2 Fix the pattern: rename methods away from their trigger strings and attach
      `@router` where a return value must route (retry cap → escalate).
- [ ] 1.3 Regression test: a flow whose testing phase fails N times must stop retrying
      after the cap and escalate — assert bounded event count, no self-trigger.
- [ ] 1.4 Re-run the 3-way Compare on `demos/02_todo_app` through the web UI with a
      fresh server.
- [ ] 1.5 Record results (all 3 backends: status, wall-clock, cost if available, smoke
      verdict) in `docs/RESULTS.md`.

### Acceptance criteria

- No method in `main_flow.py` listens to its own name.
- `retry_development`'s cap provably routes: unit test shows ≤3 dev retries then
  escalation, with total flow events bounded (e.g. <100, not 93k).
- A 3-way Compare run completes with **every backend reaching a real terminal state**
  (complete / awaiting_human / error / killed-at-timeout) and CrewAI's outcome is
  attributable to model/agent behavior, not flow wiring.
- Results table committed to `docs/RESULTS.md` with run ids traceable in
  `data/memory.db` (`GET /api/comparisons/{id}`).

---

## Step 2 — Make the numbers real (metrics + per-run cost)

Dashboard currently shows `cost_usd: null, files_generated: 0, tasks_completed: 0,
guardrails_passed: 0` during real runs. The comparison thesis is "let the data decide";
the data must exist.

### Tasks

- [ ] 2.1 Replace the process-global spend guard singleton with per-run contexts
      (`contextvars` or run_id-keyed registry). Concurrent Compare runs must not reset
      or pollute each other's budgets. CrewAI subprocess keeps its own (already isolated).
- [ ] 2.2 Wire real counters into `TeamMonitor` (or its replacement event collector):
      files_generated (from file_audit events), guardrails passed/failed/warned (from
      guardrail events), tasks completed, tests passed/failed (from test_results).
- [ ] 2.3 Surface per-run `cost_usd` + token totals from the spend context into
      `/api/runs/{id}` and the Compare columns.
- [ ] 2.4 Compare tab renders a final side-by-side table: status, wall-clock, $ cost,
      tokens, files, tests passed, smoke verdict.

### Acceptance criteria

- Launch 2 concurrent runs with different budgets: each aborts (or not) against its
  **own** ceiling; unit test proves resets don't cross-contaminate.
- A real `02_todo_app` run shows non-zero files/guardrails/tests and a non-null dollar
  cost in the dashboard, without reading logs.
- Screenshot of the Compare tab after a full run contains real numbers in every column —
  suitable for a post with zero manual annotation.

---

## Step 3 — The axe: delete/merge to ~60-65% of current size

Cut everything that dilutes the four crown jewels (multi-backend protocol, smoke gate,
operational guardrails, engineering journal). Nothing in this step lands until steps
1-2 have captured their data.

### Tasks

- [ ] 3.1 KILL `optimizers/` + `demos/06_karpathy_optimization` + `optimizer_settings.py`
      + `docs/from-karpathy-auto-research.md` (preserve on branch `archive/optimizer`).
- [ ] 3.2 KILL `rag/`, empty `knowledge/`, `scripts/ingest_knowledge.py`, RAG hooks in
      backends (`_maybe_augment_with_rag`) and config.
- [ ] 3.3 KILL the TUI (`ui/tui`) and `monitor.py`'s Rich Live rendering; reduce
      TeamMonitor to a plain thread-safe event collector (~150 LOC, no terminal UI).
- [ ] 3.4 KILL stale scripts; keep `run_demo.py`, `compare_backends.py`,
      `quickstart.sh`, `pre_push_check.sh`.
- [ ] 3.5 MERGE `memory/` down to `lessons.py` + `core/run_store.py`; drop ChromaDB
      short-term and markdown knowledge sources; drop the `crew_memory` flag plumbing.
- [ ] 3.6 SHRINK `agents/` + `tasks/` + `crews/` into `backends/crewai_backend/`
      (internal modules), mirroring how LangGraph owns `graphs/`.
- [ ] 3.7 MERGE `docs/` 24 → ~6 files: `ARCHITECTURE`, `GETTING_STARTED`, `GUARDRAILS`,
      `EVALS`, `RESULTS`, `SHOWCASE_PLAN`; move handoffs to `docs/journal/` (keep all);
      delete superseded design/UX/task docs.
- [ ] 3.8 Demos: keep `00_smoke_test` + `02_todo_app`; archive `05_microservices`.

### Acceptance criteria

- `find src -name '*.py' | xargs wc -l` total drops ≥30% from the pre-axe baseline.
- Full test suite green after every sub-step (run per sub-step, not once at the end);
  ruff + mypy clean.
- `uv run python scripts/run_demo.py demos/02_todo_app --backend <each>` still works for
  all three backends.
- No import of deleted packages anywhere (`grep -r "ai_team.rag\|ai_team.optimizers"` → 0).
- Web Compare demo path unchanged from a user's perspective.
- Deleted material recoverable: one `archive/*` branch per kill.

---

## Step 4 — Backend protocol v2: stream-first, capability-declared

Kill the 4-branch `if req.backend ==` switch in `ui/web/server.py::_execute_run`. The
protocol should absorb the differences the server currently special-cases.

### Tasks

- [ ] 4.1 Extend the `Backend` protocol: `async stream()` is the primary interface;
      add `capabilities` (e.g. `{"hitl": bool, "live_monitor": bool,
      "isolation": "thread"|"subprocess"}`).
- [ ] 4.2 Normalize event vocabulary across backends: `run_started`, `event`,
      `monitor_update`, `hitl_required`, `run_finished` — one schema, documented in the
      protocol module.
- [ ] 4.3 Rewrite `_execute_run` as a single generic loop over `backend.stream()`,
      driven by capabilities (HITL detection only when `capabilities.hitl`).
- [ ] 4.4 Consolidate CrewAI backend internals: `run()` and `_run_crewai_subprocess`
      share one setup path (spend guard, console disable, workspace scope).

### Acceptance criteria

- `_execute_run` contains **zero** `req.backend == "<name>"` branches.
- Adding a hypothetical 4th backend requires implementing the protocol only — no server
  edits (prove with a stub backend in tests).
- All existing web/websocket tests pass; live 3-way Compare re-verified once.
- LangGraph HITL (`awaiting_human`) and CrewAI hard-kill behavior unchanged.

---

## Step 5 — The surface: README, flagship demo, journal, posts

### Tasks

- [ ] 5.1 README rewrite: thesis in 2 sentences → 60-second demo GIF (Compare tab, three
      columns racing, smoke verdict, cost table) → results table → architecture diagram
      → journal links. Cut future-backends speculation and feature laundry lists.
- [ ] 5.2 Record the GIF from a real run (step 1/2 output).
- [ ] 5.3 Rehearse `quickstart.sh` on a clean clone: `git clone → quickstart → dashboard
      → Run All Backends` with zero undocumented steps.
- [ ] 5.4 `docs/journal/` index page framing the handoffs as an engineering journal.
- [ ] 5.5 Three posts in `docs/posts/` from existing material:
      (a) the CrewAI wiring-bug arc ("one line of event wiring made a framework look
      broken for three weeks"), (b) GIL starvation / subprocess isolation story,
      (c) smoke gate ("70/70 tests green, app 500s").
- [ ] 5.6 Delete stale post drafts superseded by (a)-(c); refresh
      `todo_compare_results.md` with step-1 results.

### Acceptance criteria

- A cold reader reaches a running 3-way comparison in ≤5 min from clone using only the
  README.
- README top screen contains: thesis, GIF, results table with real numbers. No dead
  links, no references to deleted subsystems.
- Each post stands alone (context, evidence, code refs), ends with a takeaway, and
  contains at least one real artifact (log excerpt, table, screenshot) from a traceable
  run.
- Journal index links every handoff chronologically with a one-line hook each.

---

## Sequencing and rules

1 → 2 → 3 → 4 → 5. Commit per completed task (commit-only, never push). Full suite +
ruff + mypy green before every commit. If a step surfaces a new bug: fix-or-file
decision goes in the journal, not silently absorbed.
