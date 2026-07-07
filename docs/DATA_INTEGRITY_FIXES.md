# Data Integrity Fixes — Comparison Panel & Results Plumbing

Findings from the live 2026-07-06 n=1 comparison run
([COMPARISON_RESULTS.md](COMPARISON_RESULTS.md), "n=1 live comparison with HITL
episode"). Each task below is a bug where **real data exists but never reaches the
API, the disk registry, or the UI** — verified by comparing `GET /api/runs/{id}`
against actual files in `workspace/{id}/` and `output/runs/{id}/`.

Distinct from [UI_UX_IMPROVEMENT_PLAN.md](UI_UX_IMPROVEMENT_PLAN.md) (layout/UX) and
[UI_UX_IMPROVEMENT_PLAN_PHASE2.md](UI_UX_IMPROVEMENT_PLAN_PHASE2.md) (responsive
design) — those are about how correct data is displayed; this doc is about the data
itself being wrong, missing, or never written.

Server: `src/ai_team/ui/web/server.py`. Backends: `src/ai_team/backends/`.

Priorities: **P0** = silently wrong data (worse than missing — looks trustworthy but
isn't); **P1** = missing data with no display consequence beyond blank cells.

---

## P0-1 LangGraph "complete" status doesn't mean tests passed

**Problem.** A run can be approved past a failing quality gate via HITL and then
reports plain `status: complete` — identical to a run whose tests genuinely passed.
The Comparison Summary table and run registry give no visual or field-level signal
that this completion was an override.

**Evidence.** 2026-07-06 run `2026-07-06_161231_write-a-single-python-module_02`:
`artifacts/testing/test_results.json` records `"passed": false"` with a
`ModuleNotFoundError: No module named 'src.calc'` (reproduced fresh with
`pytest tests/ -q` in the workspace — `tests/test_calc.py` imports `from src.calc
import ...` but `src/` is an empty directory). A human clicked Approve on the HITL
pause. The run then reported `status: complete`. First flagged 2026-07-03
([COMPARISON_RESULTS.md](COMPARISON_RESULTS.md) finding 2 in that section), now
reproduced with a concrete root cause.

**Fix.**
- Add a distinct terminal status: `complete_approved` (or similar) whenever a run
  resumes from `awaiting_human` without its quality gate having passed on the last
  attempt before the pause. Do not conflate with plain `complete`.
- Compare Summary table and Dashboard status chip must render this distinctly (e.g.
  a warning-colored chip, not the same green "complete").
- Persist which quality-gate result was in effect at approval time so this is
  auditable after the fact, not just inferred.

**Acceptance criteria.**
- [x] A run resumed via HITL approval after a failing test run reports a status value
      distinguishable from a run that passed on its own merits.
- [x] Comparison Summary table and Dashboard render the two statuses with visibly
      different styling.
- [x] Test: simulate HITL approval over a failing gate → assert
      `status != "complete"` or an explicit `approved_over_failure: true` field is set.

**Files.** LangGraph backend resume path (`src/ai_team/backends/langgraph_backend/`
or equivalent), `server.py` run-status serialization, `Compare.tsx`/`Dashboard.tsx`
status rendering.

---

## P0-2 Claude SDK results bundle — regression of a previously-fixed bug

**Problem.** Claude SDK runs write real, correct files to `workspace/{id}/` (verified:
calc.py, test_calc.py, conftest.py, `docs/test_results.json` showing genuine 5/5
passed) but `GET /api/projects/{id}/tree` returns `{"tree": []}` for **both**
`root=workspace` and `root=bundle`, and there is no `output/runs/{id}/` directory at
all. Downstream: UI shows "Tests passed: 0" for a run that actually passed 5/5, and
`monitor.phase` never advances past `"intake"`.

**Evidence.** 2026-07-06 run `2026-07-06_161231_write-a-single-python-module_03`.
Directly contradicts [journal/2026-07-04.md](journal/2026-07-04.md) fix #7: *"Claude
SDK runs were invisible to the disk registry — no `output/runs/<id>/` at all...
Fix: `_write_results_bundle()` called on both `run()` and `stream()` paths
(`887549c`)."* The exact symptom recurred despite that fix.

**Fix.**
- First: find why the fix didn't hold. Check whether the Compare-tab / web-server
  launch path calls a different entrypoint than whatever `887549c` covered (the fix
  description mentions `run()` and `stream()` — check if the web server's launch
  uses a third path, e.g. a background-task wrapper).
- Add a regression test that launches an SDK run through the **actual web server
  code path** (not a direct backend `run()` call) and asserts `output/runs/{id}/`
  exists with `state.json`/`run.json` afterward.
- Once the bundle write is fixed, separately fix `monitor.phase` to reflect the
  actual last-completed phase, not freeze at the first one.

**Acceptance criteria.**
- [x] Launching an SDK run via the web Compare tab produces
      `output/runs/{id}/state.json` and `run.json` after completion.
- [x] `GET /api/projects/{id}/tree` returns non-empty results for a completed SDK run
      matching its actual workspace contents.
- [x] `monitor.phase` for a completed SDK run reflects a terminal phase, not the
      first phase it entered.
- [x] Regression test added covering the web-launch path specifically (not just a
      direct backend unit test — this is exactly the gap that let the bug back in).

**Files.** SDK backend (`src/ai_team/backends/claude_agent_sdk/` or equivalent),
`server.py` (run-launch/background-task wiring), results-bundle writer module.

---

## P0-3 Cost data exists but never reaches the field the UI reads

**Problem.** CrewAI's real spend ($0.000614, 1 call, 1413 tokens) is correctly
recorded in a **separate top-level `spend` object** returned by `GET /api/runs/{id}`
— but `monitor.cost_usd` (the field the Comparison Summary table and Dashboard
Metrics card actually read) is `null`, even in the final terminal state. `state.json`
only ever contains the **pre-run estimate** (`estimated_cost_usd`, synthetic
per-role breakdown) — the real post-run figure is never merged into it.

**Evidence.** 2026-07-06 run `2026-07-06_161231_write-a-single-python-module_01`:
`monitor.cost_usd: null`, sibling `spend: {"spent_usd": 0.000614, ...}` present in
the same API response. Broader than the "CLI-path spend gap" noted in
[journal/2026-07-04.md](journal/2026-07-04.md) open item 1 — this was a **web-launched
Compare run**, not a CLI run, so the actual scope is bigger than previously tracked.

**Fix.**
- At run finalization, copy `spend.spent_usd` into `monitor.cost_usd` (or make the
  UI read from `spend` directly — pick one canonical source and stop having two).
- Merge the real spend into `state.json` alongside (or replacing) the pre-run
  estimate fields, so disk-level inspection shows the actual number, not just the
  guess.
- Audit whether this same disconnect affects LangGraph and Claude SDK (their
  `monitor.cost_usd` happened to populate correctly this run — confirm it's not
  coincidental/backend-specific wiring that CrewAI is simply missing).

**Acceptance criteria.**
- [x] `monitor.cost_usd` is non-null and matches `spend.spent_usd` for every
      completed run, across all three backends.
- [x] `state.json`'s cost field reflects actual spend after completion, not just the
      pre-run estimate.
- [x] Test: complete a run with known token usage → assert `monitor.cost_usd` equals
      the computed spend, not null and not the pre-run estimate.

**Files.** `server.py` (run finalization / `finish_run`), `ResultsBundle` or
equivalent finalize method, CrewAI backend's spend-tracking wiring specifically.

---

## P1-1 Comparison panel metrics blank for 2 of 3 backends (tasks/files/tests/retries)

**Problem.** Beyond cost (P0-3) and logs/guardrails ([UI_UX_IMPROVEMENT_PLAN.md](UI_UX_IMPROVEMENT_PLAN.md)
P0-6), the core progress metrics are wrong for LangGraph and Claude SDK on
completed runs: `tasks_completed`, `files_generated`, `tests_passed`, and `retries`
all read `0` despite verified real work on disk. Only CrewAI's numbers are accurate.

**Evidence.** 2026-07-06 comparison, all three runs' `monitor.metrics` from
`GET /api/runs/{id}`:

| Cell | CrewAI | LangGraph | Claude SDK |
|---|---|---|---|
| Tasks completed | 4 (correct) | 0 (real work happened) | 0 (real work happened) |
| Files generated | 2 (correct) | 0 (files exist on disk) | 0 (files exist on disk) |
| Tests passed | 5 (correct) | 0 (correctly 0 — really failed) | 0 (wrong — really 5/5) |
| Retries | 0 (correct) | 0 (wrong — really had 4 dev/test cycles) | 0 (correct) |

**Fix.**
- For LangGraph and Claude SDK, wire `monitor.metrics` to read from the same
  artifacts already proven to exist (`test_results.json`, code manifests, the
  activity log's phase-transition count for retries) rather than whatever currently
  leaves them at their zero-initialized defaults.
- This likely shares root cause with P0-2 for the SDK backend (no bundle → no data
  source to read metrics from) — fixing P0-2 may fix this for SDK as a side effect;
  verify explicitly rather than assuming.
- LangGraph's gap is separate from P0-2 (LangGraph's bundle exists and its tree API
  works) — this is specifically about `monitor.metrics` not being populated from the
  data it already has on disk.

**Acceptance criteria.**
- [x] Completed LangGraph and Claude SDK runs show non-zero, accurate
      `tasks_completed`/`files_generated` matching their actual workspace contents.
- [x] `tests_passed`/`tests_failed` reflect the real `test_results.json` content for
      all three backends (including correctly showing failure counts, not just
      successes).
- [x] `retries` reflects the actual count of retry/development-cycle log entries.
- [x] Test per backend: complete a run with known task/file/test counts → assert
      `monitor.metrics` matches.

**Files.** Per-backend monitor-population code (wherever CrewAI's correct version
lives — use it as the reference implementation — likely
`src/ai_team/backends/crewai_backend/` monitor wiring vs. the other two backends'
equivalents).

---

## P1-2 Token estimate and guardrail pass/fail/warn counts blank on all three backends

**Problem.** Unlike the backend-specific gaps above, `token_estimate` and
`guardrails_passed`/`guardrails_failed`/`guardrails_warned` are `0` across **all
three backends** unconditionally, even on runs with verified retry/guardrail
activity in their logs. This isn't backend-specific — nothing in the shared pipeline
appears to ever populate these two field groups for any backend.

**Evidence.** 2026-07-06 comparison, all three `monitor.token_estimate` values are
`0`; all three `guardrails_passed/failed/warned` triples are `0/0/0` regardless of
backend, including CrewAI whose other metrics (tasks/files/tests) are otherwise
accurate.

**Fix.**
- Locate where `token_estimate` is supposed to be computed (likely from the same
  token-count data already used for cost calculation in P0-3 — token counts exist in
  the `spend` object, e.g. `total_tokens: 1413`) and wire it into
  `monitor.token_estimate`.
- Locate where guardrail events are supposed to be counted and tallied into the
  passed/failed/warned totals — check if this is the same root cause as
  [UI_UX_IMPROVEMENT_PLAN.md](UI_UX_IMPROVEMENT_PLAN.md) P0-6 (guardrail *events*
  list is empty) — if the events list is never populated, the counts derived from it
  will always be zero too. Fixing P0-6 first may resolve this as a side effect;
  verify explicitly.

**Acceptance criteria.**
- [x] `monitor.token_estimate` is non-zero and reasonably close to the token count in
      the `spend` object, for all three backends.
- [x] Guardrail pass/fail/warn counts are non-zero for any run with actual guardrail
      activity in its log (e.g. LangGraph's HITL escalation implies guardrail/gate
      activity that should be countable).
- [x] Test: run with known guardrail events → assert counts match; run with known
      token spend → assert `token_estimate` is populated.

**Files.** Shared monitor-population code path, guardrail event tracking (check if
shared with [UI_UX_IMPROVEMENT_PLAN.md](UI_UX_IMPROVEMENT_PLAN.md) P0-6's fix).

---

## P1-3 Tree API is CrewAI/LangGraph-correct, Claude-SDK-specific-broken

**Problem.** Not a new task on its own — this is the confirming contrast for P0-2.
CrewAI's tree API works correctly for both `root=workspace` and `root=bundle`
(returns real files: `calc.py`, `tests/test_calc.py`, full `artifacts/` tree,
`reports/` including `manager_self_improvement_report.md`). LangGraph's tree API
also works for both roots. Only Claude SDK's tree/registry path is broken.

**Fix.** No separate fix needed beyond P0-2 — this finding exists to scope P0-2's
investigation: **do not touch the shared tree-serving code** (it's proven correct
for 2/3 backends), focus exclusively on the Claude SDK backend's registry-write
path.

**Acceptance criteria.** Covered by P0-2's acceptance criteria.

**Files.** None beyond P0-2 — this is a scoping note, not an independent change.

---

## Suggested order

1. **P0-2** (Claude SDK regression) first — it's the most severe (a previously-fixed
   bug came back) and P1-1/P1-3 both partially depend on understanding its root
   cause.
2. **P0-1** (HITL-approved-but-failing status) — independent of P0-2, high severity
   because it makes the comparison table actively misleading, not just incomplete.
3. **P0-3** (cost field wiring) — independent, mechanical fix once the canonical
   source (`spend` vs `monitor.cost_usd`) is decided.
4. **P1-1** (per-backend metrics) — verify what P0-2 fixed for free on the SDK side,
   then fix LangGraph's gap explicitly.
5. **P1-2** (tokens + guardrail counts) — check dependency on
   [UI_UX_IMPROVEMENT_PLAN.md](UI_UX_IMPROVEMENT_PLAN.md) P0-6 before implementing
   separately.
