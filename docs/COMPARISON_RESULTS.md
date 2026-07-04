# Backend Comparison Results

## First post-wiring-fix 3-way comparison — 2026-07-01 evening

- **Comparison id:** `432ec61f-0d2c-48ad-a10d-b724f748d588` (`GET /api/comparisons/432ec61f-...`)
- **Brief:** `demos/02_todo_app` (Flask + SQLite TODO app, SPA frontend, Docker, pytest)
- **Context:** first 3-way run after the CrewAI flow-wiring fix (`dabef2b` — self-triggering
  listeners eliminated, retry caps actually route) and the CrewAI subprocess isolation +
  hard-kill (`c4a2e53`). See [SHOWCASE_PLAN.md](SHOWCASE_PLAN.md) step 1.
- **Launched:** 21:07 local, all three concurrently through the web Compare tab
  (distinct run ids — the run-id TOCTOU collision fix `157841a` held).

| Backend | Status | Wall-clock | Smoke | Dev retries | Notes |
|---|---|---|---|---|---|
| claude-agent-sdk | ✅ complete | 18m 22s | ✅ 6/6 endpoints, booted | 0 | Full success: all phases, Dockerfile + docker-compose present, health/CRUD round-trip green. |
| langgraph | ⏸ awaiting_human | ~50m to interrupt | — (never reached deployment) | 3/3 exhausted | Real, designed HITL escalation via `interrupt()` — surfaced in the API **within ~1 min** (vs 78 min the previous night when CrewAI's in-process thread starved the GIL; subprocess isolation validated). Run was **blocked-slow by recurring scope-guardrail false positives** on QA-vocabulary output (relevance 15%, then 4%, vs 25% floor — flagged words literally: *coverage, suite, testing, validation, test*), plus one recovered deepseek malformed-JSON crash (salvage extracted `docker-compose.yml`). Orchestration sound; guardrail precision is the fix (queued: add `qa_engineer` to `_LOW_SCOPE_RELEVANCE_ROLES`). |
| crewai | ⏱ error (timeout-killed) | 900s (hard cap) | — | 0 runaway | **Headline: the retry-recovery path survived for the first time.** Hit its usual malformed-JSON dev failure at 21:14:40, entered retry backoff, and cleanly re-ran development 2s later — the exact spot that previously meant a silent hang or a 93,284-iteration self-trigger runaway. Zero `retrying_development` runaway this run. Was mid-LLM-call, still progressing, when the 900s subprocess hard-kill fired (clean kill, correct error propagated). Verdict rewritten: **slow on deepseek, not broken** — 900s is tighter than the SDK's 18m; use `CREWAI_HARD_TIMEOUT_SECONDS=1800` for a fair rerun. |

### What this run proved

1. **The flow-wiring fix works live** — 0 runaway retries vs 93,284 the previous run.
   Three handoffs of "CrewAI deadlocks in retry" traced to `@listen("X") def X`
   self-triggering plus dead-code retry returns; both eliminated.
2. **Subprocess isolation works live** — CrewAI's kill was clean and on-deadline, and
   LangGraph's HITL interrupt surfaced in ~1 minute because no sibling thread could
   starve the GIL.
3. **The comparison's top remaining blocker moved**: it's now the scope-guardrail
   QA-vocabulary false positive (LangGraph burned ~20+ min of retry cycles on it), not
   CrewAI's runtime.

### Next (per SHOWCASE_PLAN)

- Fix scope-guardrail false positive (`qa_engineer` → low-relevance roles), bump CrewAI
  budget to 1800s, rerun for a shot at the first all-three-green comparison.
- Wire real cost/metrics into the dashboard (step 2) so the next table carries $ and tokens.

---

## Second post-fix comparison — comparison_id `63e7f8a0`, launched 22:02 same evening

All fixes live: flow wiring (`dabef2b`), scope-guardrail code-stripping (`1b7bd6d`),
CrewAI budget doubled to 1800s.

| Backend | Status | Wall-clock | Smoke | Dev retries | Notes |
|---|---|---|---|---|---|
| claude-agent-sdk | ✅ complete | **12m 48s** | ✅ PASS 8/8 (gunicorn; health, CRUD round-trip, validation, 404s) | 0 | Fastest run yet (was 18m22s on the same brief 1h earlier — same-config variance is real; see "n≥5 runs" below). |
| langgraph | ⏸ awaiting_human | ~47m to interrupt | — | 3/3 exhausted | **Scope false positives GONE** — code-stripping held through all dev phases (0 scope failures until testing). Testing then hit a **new, confirmed false-positive class**: `role_adherence` flagged QA writing `tests/conftest.py` — a *pytest standard file*, verified on disk — as "production source" under the test_*.py-only rule; 3/3 retries burned, escalated. Patch queued: allow `conftest.py`/`fixtures*.py`/`__init__.py` for the QA role. (Scope floor also recalibrated 0.25→0.15 in `2aa9870` from this run's 18% readings; applies next restart.) |
| crewai | ⏱ error (timeout-killed) | 1800s (hard cap) | — | 0 runaway | Double the budget, still unfinished — now a clean **performance** verdict: deepseek + heavy quality-guardrail retry cycles (type hints, CodeFile parse) simply don't converge on this brief in 30 min. Orchestration sound throughout: survived multiple dev-error recoveries, zero runaway, clean on-deadline kill, correct error propagation. |

### Fix scoreboard (what two consecutive live runs proved)

| Fix | Verdict |
|---|---|
| Flow wiring (`dabef2b`) | **Held** — 0 runaway retries in both runs (was 93,284). |
| Subprocess isolation + hard kill (`c4a2e53`) | **Held** — two clean on-deadline kills; no GIL starvation of sibling runs (LangGraph HITL surfaced in ~1 min both times). |
| Run-id atomic reservation (`157841a`) | **Held** — distinct ids/workspaces in both concurrent launches. |
| Scope code-stripping (`1b7bd6d`) | **Partial → recalibrated** — eliminated dev-phase false positives; QA prose still scored 18% vs 25% floor; floor recalibrated to 0.15 (`2aa9870`) from live data. |
| New discovery | `role_adherence` false-positive class: standard pytest support files trip the test_*.py-only rule. Two new failure-taxonomy entries tonight. |

---

## Third post-fix comparison — comparison_id `9efb6583`, launched 23:09 same evening

All patches live: flow wiring (`dabef2b`), scope code-stripping (`1b7bd6d`), scope floor
0.15 (`2aa9870`), QA conftest allowlist (`ad6c62e`), CrewAI 1800s.

| Backend | Status | Wall-clock | Smoke | Dev retries | Notes |
|---|---|---|---|---|---|
| claude-agent-sdk | ✅ complete | **12m 44s** | ✅ passed 8/8, booted | 0 | Second consecutive ~13-minute success on this brief — repeatability signal. |
| langgraph | ⏸ awaiting_human | 11m to interrupt | — | 3/3 exhausted | **Zero guardrail false positives** — all three guardrail fixes held. Root cause is the *original* §8 failure class: deepseek's QA agent never called `file_writer` (workspace `tests/` empty). The **§8 re-prompt lever fired 3× — its first live verification** (fires exactly once per testing attempt, falls back cleanly; insufficient against full model degeneration, as designed-for). Three clean graph-level retries, then a proper `interrupt()` escalation surfaced in the API within a minute. |
| crewai | ⏱ error (timeout-killed) | 1800s (hard cap) | — | 0 runaway | Still writing real code (`backend/app.py` at 23:21, 20KB LLM responses at 23:34) when the deadline hit. Third consecutive clean on-deadline kill. |

### Key findings

1. **Zero platform bugs remain in the loop.** For the first time, every outcome is
   attributable to model/agent behavior, not orchestration or harness defects:
   Claude Agent SDK + Claude succeeds repeatably (~13 min ×2); LangGraph + deepseek is
   blocked by QA tool-call degeneration and *escalates cleanly*; CrewAI + deepseek makes
   real progress but cannot converge within 30 minutes.
2. **§8 re-prompt lever live-verified** — handoff-2026-07-01 open item #1 closed.
3. **The model confound is now the dominant variable.** The comparison currently measures
   framework+model pairs (SDK runs Claude; the others run deepseek). The next scientific
   step is a same-model matrix plus n≥5 runs per configuration for variance — see the
   strategic notes in [SHOWCASE_PLAN.md](SHOWCASE_PLAN.md).

---

## Same-model matrix — first pass (langgraph × claude-sonnet-4, 2026-07-02 morning)

The three-run comparison above measures **framework+model pairs** (SDK runs Claude, the
others run deepseek). First pass at breaking the confound: the `full-claude` team
profile pins all 9 roles to `anthropic/claude-sonnet-4` via OpenRouter
(`model_overrides`, override chain verified), run through LangGraph on the same
`demos/02_todo_app` brief, headless CLI, n=4.

**Baseline to beat:** LangGraph+deepseek wrote **zero test files in 3/3 runs** (QA
narrated instead of calling `file_writer`) and every run ended `awaiting_human`.

| Run | Status | Elapsed | Tests written | $ spend | Provider errors | Blocker |
|---|---|---|---|---|---|---|
| 1 | budget-abort | 15m17s | ✅ 10 files + conftest | $5.15 (86 calls) | 133 | $5 deepseek-era ceiling + Vertex tool-id 400s |
| 2 | budget-abort | 29m08s | ✅ (full phase progression, 19 dev files, 2 test cycles) | $10.05 (113 calls) | 133 | Vertex tool-id 400s burned budget |
| 3 | awaiting_human | 17m20s | ✅ 4 suites + conftest | <$8 | **0** (fix validated) | **Harness dependency gap** (below) |
| 4 | budget-abort | 20m16s | ✅ suites + conftest | $8.03 (122 calls) | 27 (Bedrock-side) | Budget + residual provider retries |

### Verdict

1. **The model confound is mechanically confirmed.** Claude called `file_writer` and
   produced real test suites in **4/4 runs** vs deepseek's **0/3**. The §8
   "QA degeneration" failure class is a *model* property, not a LangGraph property.
   None of the four claude runs failed the way deepseek fails — every remaining blocker
   was a harness or provider-ops class.
2. **New ops finding — provider-routing dialect breakage.** OpenRouter served
   `anthropic/claude-sonnet-4` from Google Vertex + Amazon Bedrock only on this key (a
   hard pin to provider "Anthropic" 404s — endpoint pools are account-specific).
   Vertex's Anthropic-translation layer rejected tool-call ids with 400s — 133
   retry-errors per run until steering `ignore=["Google"]` (validated: run 3 had 0).
   Bedrock also throttled/errored occasionally (run 4: 27). Multi-provider routing is
   itself a failure surface for tool-calling agents.
3. **New ops finding — spend budgets are model-dependent.** The $5 default ceiling was
   calibrated on deepseek prices; sonnet runs cost $5-10+ on this brief. The per-run
   spend guard fired **correctly and cleanly all three times** (run_id-scoped,
   yesterday's fix) — the guard working is the success story; the calibration is config.
4. **New harness finding — quality-gate dependency gap.** Run 3's tests died on
   `ModuleNotFoundError: flask_sqlalchemy` ×4 modules: the quality gate runs pytest in
   the *harness* venv and never installs the generated `requirements.txt`. deepseek runs
   dodged it only by picking plain `flask` (already installed). Fix queued: install the
   generated requirements into an isolated per-workspace env before the gate runs.

**Net:** with the model held constant, LangGraph's pipeline works — agents plan, write
code and tests, and the failures move up the stack to provider routing, budget
calibration, and gate-environment fidelity. Exactly the "harness > model > framework"
ranking the failure taxonomy predicts, now with matrix evidence.

---

## First all-three-green comparison — smoke profile, 2026-07-03 afternoon

- **Comparison id:** `9aadf654-4888-40e5-8c56-a251bd73e756`
- **Brief:** `demos/00_smoke_test` (calc.py with add/subtract/multiply/divide +
  divide-by-zero ValueError, test_calc.py with pytest cases) — **smoke profile, Simple**
- **Context:** first comparison launched after the four parallel-worktree fixes merged
  earlier today (run_id fresh-root reservation, workspace double-nesting, CrewAI monitor
  backfill, Compare reload persistence — see journal Jul 3). Launched 14:09 local via
  the web Compare tab, all three concurrently.

| Backend | Status | Wall-clock | Tests | Cost (observed) | Notes |
|---|---|---|---|---|---|
| claude-agent-sdk | ✅ complete | **3m 03s** | ✅ 5/5 (workspace `docs/test_results.json`) | $0.70 | Fastest. Clean phase narration in activity log; wrote `src/calc.py` + `tests/test_calc.py` + docs bundle. |
| crewai | ✅ complete | 6m 50s | ✅ 5/5, **100% line+branch coverage** (`state.json`) | ~$0.03 (token table) | **First green CrewAI smoke ever** — the scenario that hung at 12min/140min pre-fix. One guardrail retry cycle (code-review 1-critical false positive, 3/4 attempts) then orchestrated-pytest salvage delivered the pass. 4 tasks, 2 files. |
| langgraph | ✅ complete | 8m 41s | ✅ 5/5 + ruff clean (`state.json`) | $0.07 | Slowest this time (usual winner at ~60s) — three bounded `retry_development` cycles before tests landed; caps held, no runaway, clean complete. |

Screenshots (docs/images/): `compare-2026-07-03-{crewai,langgraph,claude-sdk}-{files,tests}.png`

### Data-integrity findings (the actual yield of this run)

All three backends produced real, verified artifacts on disk — but the run exposed a
consistent theme: **the data exists; the display/normalization layer loses it.**

1. **Claude SDK Compare column froze mid-run** — stuck at "3m 2s / ACTIVE / 0 done"
   permanently while the backend completed at 14:12:29. The `/ws/run` terminal event
   never reached the column. Same class as the CrewAI zeros fixed this morning, different
   socket path. **Open bug.**
2. **LangGraph metrics never populate** — Compare column showed 0 tasks / 0 files at
   completion despite writing files and passing tests. Needs the same monitor backfill
   CrewAI got in `2388bca`. **Open bug.**
3. **LangGraph writes test results in its own schema** — `state.json` has
   `{'passed': True, 'lint': {...}, 'tests': {...}}` instead of the normalized
   `test_results.json` the Artifacts UI reads → UI says "No structured test results
   found" for a run with 5/5 green + clean ruff. **Open bug (normalization).**
4. **Claude SDK writes no output bundle** — no `output/runs/<id>/` dir, absent from the
   disk registry; its results live only in the workspace. **Open bug (ResultsBundle
   never invoked on the SDK path).**
5. **`run.json` has `completed_at: null` and `costs.jsonl` is empty** for both runs that
   do have bundles — cost figures above are from the live UI/spend registry, not the
   bundle. **Open bug (writer lifecycle).**
6. Cosmetic: CrewAI Tests tab badge says "0% line coverage" while `state.json` records
   100/100 line+branch; Compare column sub-header stays "Waiting for agents to join the
   run…" after completion.

**Net:** orchestration-layer verdicts from the taxonomy hold (all three complete a
simple brief; caps and kills work). The failure class du jour is one rung higher —
*results plumbing*: five distinct spots where real data on disk fails to reach the
registry, the bundle, or the screen.

### Live rerun with full screenshot trail — comparison `dfad2828`, 17:03 same day

Rerun of the same brief, this time watched end-to-end in the Compare tab with the
operator in the loop. Same-day, same-config variance turned out to be the story:

| Backend | Status | Wall-clock | Tests (disk truth) | Notes |
|---|---|---|---|---|
| claude-agent-sdk | ✅ complete | **3m 21s** | 5/5 in workspace, but files **duplicated across root, `src/`, and `tests/`** (messier than the 14:09 run) | Consistent winner on speed. Still writes no output bundle. |
| crewai | ✅ complete | 10m 41s | ✅ 5/5, phase complete (`state.json`) | 4 min slower than its own 14:09 run — code-review guardrail burned retries on a "1 critical" finding (attempt 2/4 observed) before orchestrated pytest salvaged. Second consecutive green smoke. |
| langgraph | ⚠️ complete **by operator approval** | 23m 13s (6m 43s to HITL + ~7m operator wait + resume) | `state.json`: **`passed: False`, phase `testing`** | Escalated to human review from testing after bounded retry cycles; approved mid-run; resumed and reported "complete" — but the quality gate never actually passed. Dev and QA also disagreed on test layout again (`test_calc.py` at root vs `tests/test_calculator_{basic,operations}.py`). |

Screenshot trail (docs/images/): `compare-2026-07-03-live-{launch,midrun,claude-done,langgraph-hitl,crewai-done,langgraph-done,final}.png`

**New findings from running it live:**

1. **HITL approve is a two-step UI trap.** Clicking "Approve" only pre-fills the
   response textarea; nothing is sent until "Submit & Resume". The first click looks
   accepted (no error, no state change) and the run stays paused indefinitely — an
   operator who walks away here loses the run to the void. Needs either one-click
   approve or an explicit "not sent yet" indicator. **Open bug (UX).**
2. **"Complete by approval" is indistinguishable from "complete by passing".** The run
   registry and Compare column both say `complete` for a run whose own `state.json`
   records `passed: False` in phase `testing`. The approval override should be a
   distinct terminal status (or at least surfaced) — otherwise the comparison table
   over-reports green. **Open bug (semantics).**
3. **Cross-run workspace leak is still live on a non-CrewAI path.** An empty directory
   named with the *claude-sdk* run's id appeared inside the *langgraph* run's workspace
   at launch. The morning fix (`43d66d2`) covered CrewAI's env fallback; some other
   component (SDK backend or server-side run-dir creation) still resolves a sibling
   run's workspace root. **Open bug (isolation).**
4. **Same-config variance is large at this scale**: CrewAI 6m50s → 10m41s and LangGraph
   clean-complete → HITL-escalation between two runs an hour apart, same brief, same
   models. Single-run comparisons at smoke scale are anecdotes; the n≥5 rule from the
   same-model matrix applies here too.
5. **HITL panel doesn't clear after resume.** The LangGraph column kept showing "HUMAN
   REVIEW REQUIRED" with live Approve buttons for minutes after the run had resumed and
   completed — only a page reload cleared it. **Open bug (staleness).**
6. **Validated live: the reload-reattach fix (`4ce7dce`) works.** Reloading /compare
   mid-comparison reattached both columns from the server (elapsed, cost, phase strip
   repopulated; stale HITL panel cleared). The morning's fix, exercised for real within
   eight hours of merging. Residual quirk: the reattached SDK agent row still reads
   "ACTIVE" and elapsed keeps ticking for terminal runs.

### n=5 variance batch — 2026-07-04

The two single-run comparisons above disagreed with each other within an hour; this is
the n≥5 batch the tables should have been built from all along
(`scripts/run_smoke_batch.py`, CLI path via `run_demo.py`, smoke profile, same brief;
raw rows in `output/smoke_batch_20260704_*.json`).

| Backend | Green | Wall min / median / max | Spend/run | Failure modes |
|---|---|---|---|---|
| claude-agent-sdk | **5/5** | 2m20s / 3m17s / 3m47s | $0.48–$0.95 (median $0.71) | — |
| crewai | **5/5** | 6m50s / 9m07s / 11m57s | n/a (CLI spend gap) | — |
| langgraph | **1/5** | 1m25s / 3m55s / 5m08s | n/a (CLI spend gap) | 2× lint-gate on auto-fixable style (F401 unused import; W293 whitespace) — one of them with **pytest 5/5 green**; 3× pytest `collected 0 items` (dev/QA test-layout mismatch) |

**What n=5 shows that n=1 could not:**

1. **CrewAI's demotion verdict is due for correction.** Counting the two Jul 3
   comparison runs, CrewAI is now on a **7-run green streak** on the scenario that had
   *zero successful baselines* on Jun 30 ("hangs at 12min/140min, kill -9 only"). The
   flow-wiring + subprocess-isolation + salvage fixes didn't just stop the bleeding —
   they made it the second-most-reliable backend on this brief. Slow (2-3× SDK
   wall-clock, widest spread: 6m50s–11m57s), but consistently green.
2. **LangGraph's 1/5 is not one bug, it's two classes.** (a) The ruff lint gate fails
   runs for auto-fixable style noise — including a run whose tests were 5/5 green;
   a `ruff --fix` pass before the gate (or gating on `check --fix --diff` cleanliness)
   would have flipped 2 of 4 failures. (b) The dev/QA file-layout disagreement
   (`collected 0 items`, 3×) is the old coordination problem from Jun 28 — planning
   needs to pin the test layout into both prompts. Its one green run (1m25s) matches
   the historical 60-77s baseline: when it works, it's the fastest by far.
3. **SDK is the consistency champion, at a price.** Tightest wall-clock spread
   (2m20s–3m47s), 5/5 green, but $0.48–$0.95/run vs pennies for the deepseek backends —
   a 2× spend variance between identical runs is itself worth knowing.
4. **Remaining plumbing gap (honest ledger):** CrewAI/LangGraph CLI runs still write no
   `costs.jsonl` (the finalize hook fires on the web path and the SDK backend only),
   and the batch runner had to normalize **three** different `test_results` schemas.
   Both stay on the open list.

---

## Historical results

Earlier comparisons (pre-wiring-fix) are described in
[journal/2026-07-01.md](journal/2026-07-01.md) (§11 and the demo status table) and
[posts/todo_compare_results.md](posts/todo_compare_results.md) (2026-06-26 CLI/eval run).
