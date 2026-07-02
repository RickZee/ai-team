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

## Historical results

Earlier comparisons (pre-wiring-fix) are described in
[handoff-2026-07-01.md](handoff-2026-07-01.md) (§11 and the demo status table) and
[posts/todo_compare_results.md](posts/todo_compare_results.md) (2026-06-26 CLI/eval run).
