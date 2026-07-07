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
| [journey.md](journey.md) | Running meta-narrative across sessions. |

The 2026-07-01 late-evening arc concluded in
[COMPARISON_RESULTS.md](../COMPARISON_RESULTS.md): the flow-wiring self-trigger bug
(93,284-iteration runaway → 0), two guardrail false-positive classes fixed with live
evidence, and the first comparison where every backend's outcome was attributable to
model behavior rather than platform defects. The distilled version is
[posts/failure-taxonomy.md](../posts/failure-taxonomy.md).
