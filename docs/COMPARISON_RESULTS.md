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

## Historical results

Earlier comparisons (pre-wiring-fix) are described in
[journal/2026-07-01.md](journal/2026-07-01.md) (§11 and the demo status table) and
[posts/todo_compare_results.md](posts/todo_compare_results.md) (2026-06-26 CLI/eval run).
