# Engineering Journal

Session-by-session handoff notes from building and debugging this system — kept
verbatim, failures included. Most "multi-agent" write-ups show the demo that worked;
this is the record of what it actually took: root-cause investigations, wrong turns
corrected in later entries, and fixes verified against live runs.

| Entry | One-line hook |
|---|---|
| [2026-06-24](2026-06-24.md) | First eval-framework session; three backends under one harness. |
| [2026-06-25](2026-06-25.md) | Parallel evals, CrewAI Rich-console recursion, deepseek tool non-compliance — 20 fixes in a day. |
| [2026-06-26 (evals)](2026-06-26-evals.md) | The "CrewAI infinite retry loop" flagged as top priority — root cause found five days later. |
| [2026-06-26 (general)](2026-06-26-general.md) | Parallel general-track session, same day. |
| [2026-06-28](2026-06-28.md) | The core agentic failure: models writing code as prose instead of calling tools. Salvage, spend guards, bounded loops. |
| [2026-07-01](2026-07-01.md) | Web Compare tab end-to-end: six bugs found and fixed live, CrewAI verdict corrected, run history persisted. §11: run-id TOCTOU race + GIL-starvation discovery + subprocess isolation. |
| [2026-07-02](2026-07-02.md) | The big one: flow self-trigger root cause (93k-iteration runaway → 0), three live comparisons to zero platform bugs, failure taxonomy, −12.6k-line axe; morning: same-model matrix confirms the confound — claude writes tests 4/4 where deepseek wrote 0/3. |
| [2026-07-04](2026-07-04.md) | n≥5 batch runner, twelve results-plumbing fixes, CrewAI 5/5 green streak. |
| [2026-07-06](2026-07-06.md) | LangGraph run identity: GUID workspace litter traced to graph tests, `RunSession` + intake binding, post-run moved out of graph, test harness isolation. |
| [2026-08-16](2026-08-16.md) | The taxonomy becomes executable: Trace boundary, FM-001…010 bound to deterministic checks, $0 Tier A gate in CI — and the four things deliberately left undone. |
| [2026-09-12 (alignment)](2026-09-12-harness-alignment.md) | New FM-014…017 scored retroactively; historical traces inconclusive (no acceptance / pressure / QA verdicts yet). |
| [2026-09-12 (arms)](2026-09-12-harness-alignment-arms.md) | Ladder arms + report; live spends not run; punchline rewritten to four of seventeen. |
| [2026-09-13 (alignment CI)](2026-09-13-harness-alignment-ci.md) | Every suite/CI failure found landing harness-alignment, and the first-run risks if Actions is red. |
| [2026-09-13 (eval audit)](2026-09-13-eval-methodology-audit.md) | The corpus audit: 50 traces with 0 spans, 0 annotations, 0 of 17 failure modes observed — and the prompt line that made error analysis impossible. |
| [2026-09-13 (LangGraph smoke)](2026-09-13-langgraph-smoke-eval.md) | First live eval case: path-sandbox crash + lexical guardrail retry storm; traces still starved; 9.1 not published. |
| [2026-09-13 (UI refinement)](2026-09-13-ui-refinement.md) | Token/CSS split, frozen testids, Playwright heading-level miss, migrator residue; after-state screenshots (0.1 reconstructable from `87600d2`). |
| [2026-09-14 (check liveness)](2026-09-14-check-liveness.md) | 76% of the check suite abstains and nothing reported it; two span types have no producer at all; a four-stage workbench for the human half of the loop. |
| [2026-09-15 (course and testbed)](2026-09-15-course-and-testbed.md) | The course could not be written because the loop cannot be run here — 7 breaks on the stranger's path, 4 before the first eval; two specs and an execution order; FM-021 confirmed at n=308. |
| [2026-09-16 (course v2)](2026-09-16-course-v2.md) | Six predict→run→observe labs with raw commands, 8 illustrations; backfill no longer labels every run `crewai` — unrecorded backends are now `unknown`; the second reader is wrong too; `/test-course` agent with a $10 spend plan — pilot says week 4 can't be done from a fresh clone; first real test run fixed the watchdog, Claude budget and the LangGraph guardrail loop. |
| [2026-09-17 (drafts never committed)](2026-09-17-drafts-never-committed.md) | Behind the fixed guardrail loop: since 08-28 no agent write was ever saved (draft-then-commit had no committer), QA lacked `file_writer`, and unit tests ran with drafts off. Fixed — then the first live run finished in 12.4 min and used all 3 retries on correct code: a silent `test_*.py` relocation duplicating the suite, the gate linting generated code by this repo's house style, and QA with no read tool. Those fixed, all three backends complete live (LangGraph 3.8 min, retry 0), plus the reporting bugs behind the numbers: an 89× CrewAI spend under-report, a 6 ms clock on a 217 s run, and a test suite writing into the eval corpus. |
| [2026-09-28 (cloud foundation)](2026-09-28-cloud-backend-foundation.md) | The contract the two cloud backends have to pass: conformance suite, harness-owned accepts, tool bridge, OTel import. Docker dashboard and `terraform plan` still open. |
| [2026-09-30 (repo audit)](2026-09-30-repo-audit.md) | Declared vs. exercised: 17 unimported deps, 36 adversarial tests CI never ran, a secret detector blind to the repo's own key formats, a harness layer marked *enforced* that nothing calls. 18 fixed, 14 open with sources. |
| [journey.md](journey.md) | Running meta-narrative across sessions. |

The July rigor arc (Jul 21–24) has no standalone entry — it lives in
[journey.md](journey.md): an adversarial review that found the judge sharing a vendor
with a contestant, n=5 rankings that don't survive their own Wilson intervals, a
model/framework confound in the published table, a labeled guardrail corpus that caught
two shipped defects on first run, and `$0` replay mode so a contributor can validate the
harness without paying to exercise it.

The 2026-07-01 late-evening arc concluded in
[COMPARISON_RESULTS.md](../COMPARISON_RESULTS.md): the flow-wiring self-trigger bug
(93,284-iteration runaway → 0), two guardrail false-positive classes fixed with live
evidence, and the first comparison where every backend's outcome was attributable to
model behavior rather than platform defects. The distilled version is
[posts/failure-taxonomy.md](../posts/failure-taxonomy.md) — now also machine-readable as
[`evals/taxonomy/failure_modes.yaml`](../../evals/taxonomy/failure_modes.yaml)
(FM-001…FM-010), with method and limitations in
[EVAL_METHODOLOGY.md](../EVAL_METHODOLOGY.md).
