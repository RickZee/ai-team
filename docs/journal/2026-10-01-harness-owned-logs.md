# 2026-10-01 — The harness writes its own logs

**A model-off run finished and left `logs/` empty. Every writer for those logs now lives in the harness, a stopped run keeps its last checkpoint, and a passing gate marks acceptance.** Each change has a test that fails on the old code.

**Author:** Rick Zakharov (with agent assist)
**Preceded by:** [2026-09-30 repo audit](2026-09-30-repo-audit.md). Its 14 open items stand; none were in scope here.
**Branch:** `feature/field-notes-sequel`, from `1701918` (`main` at the time).

---

## 1. What was found

| Finding | Verified how | Consequence |
| --- | --- | --- |
| Placeholder dry run, model off: exit 0, `completed_at` set, `logs/` empty | Ran `scripts/run_demo.py … --graph-mode placeholder` into a temp dir on 2026-09-30 | The bug in §3 |
| 369 run records; 240 without `completed_at`, 241 without `costs.jsonl` | Directories that contain `run.json` (a raw directory count is 385) | Old records stay as they are; the fix does not rewrite history |
| The seven timeouts in the Sep 18 batch have no `state.json` | Each timeout run dir holds `logs/costs.jsonl` only | Their cause cannot be read from phase history (§2, `a53b385`) |
| Sep 18 batch, 30 runs on LangGraph, team `smoke`: 22 complete, 7 timeout, 1 failed; Wilson 95% 55.6–85.8%; median spend $0.0214; median wall 12.4 min | `output/smoke_batch_20260918_225130.json` | The baseline for the re-measure |
| Per-role split on the 19 runs whose messages cover ≥ 90% of their tokens: QA 89.6% (in:out 43.4), developer 10.1%, architect 0.3% | Re-summed token usage in those `state.json` files | No command printed it; now `scripts/role_cost.py --batch` does |
| CrewAI's 93,284-iteration listener loop and the 78-minute GIL hang are two incidents | `docs/posts/failure-taxonomy.md` §2, `docs/troubleshooting/gil-starvation-hitl-delay.md` | `docs/FRAMEWORKS.md` states them as two fixes |
| Old relevance scoring fails correct QA code at 8% | The regression fixture's message | The figure is the test, not a rounded memory |
| `eval-methodology-alignment` tasks 1.1–1.6 are not done | The spec still wants `session.json`, one writer module and a backend wrapper | `TelemetryWriter` is a start; those boxes stay unchecked |

## 2. What changed

| Commit | Decision |
| --- | --- |
| `cc684de` | A finished run always writes `logs/costs.jsonl`. No model calls is `spent_usd: 0`, `writer: harness`. The closer used to skip the file when `calls` was 0, which is every mocked run |
| `e8973e6` | LangGraph appends `phase_history` on the placeholder nodes and writes `phases.jsonl` from it. The orchestrator prompt no longer asks the model to write the file |
| `d7e0bf2` | A placeholder run leaves an empty `audit.jsonl` through the bus's own path. Placeholder only: no node there can call a tool, so zero is known |
| `7e5d177`, `eeaa9fb` | A passing quality gate calls `mark_passing` with verifier `_harness`; a failing gate leaves `passes` false. The September items stay false: they are the old record |
| `160796c` | Deleted 22 `__fixture.json` files byte-identical to a sibling already in the corpus: 72 trace ids, 72 files. A test fails if an id repeats |
| `be661e0`, `5637bfa` | `scripts/role_cost.py` splits tokens by role for one run or a batch, keeps runs whose messages reach 90% of the cost log's total, and lists every skipped run with its reason. Dollars per role are a token share of the run total, and the report says so |
| `a53b385`, `7a49cc1` | A stopped LangGraph run keeps its last checkpoint: when `DemoTimeoutError` unwinds out of `graph.invoke`, the backend writes the checkpointer's state with `stopped_by` and `stopped_in`, writes `phases.jsonl` from it, and re-raises (`ai_team.harness.stopped_run`). Checked with a real SIGALRM: stopped in `testing`, three phases recorded. The batch runner never counts a stopped run as green. 11,867 LOC under `ignore_errors`; the ratchet moves down |
| `2c4cb28` | `docs/FRAMEWORKS.md`: where each backend keeps state, resumes, waits for a human and failed. `ARCHITECTURE.md` §2.1.1 links to it |
| `6bf2e8c` | Course week 1 shows the dry run as it behaves after the fixes; week 3 keeps its "before" image of self-reported telemetry |
| `e2d3d55` | `test_annotate` looks fixtures up by the one file left per trace id |

## 3. The thing worth naming on its own

**A missing cost file was treated as "this run did not happen," and a mocked run never created one.** `run_demo` passed `spend=None` whenever `calls` was 0, and `finalize` wrote `costs.jsonl` only when that argument was truthy. Charts that skip absent files then drop the free runs, which are the runs you use to test the instrument.

Found by running the week-1 command into a temp directory and listing `logs/`. A test that finalized with no spend and asserted the file was absent would have locked the bug in. That was the old test; it now requires a zero row.

The phase log had the same shape: its writer was a sentence in a prompt. Deleting the sentence without a harness writer would have made the file rarer, so the prompt line came out in the same commit that writes the file from `phase_history`.

## 4. What did not change

- No new finish rate. A re-measure needs a paid batch (§6).
- `emit_phase_end` in `context_pressure.py` still writes `phases.jsonl` on the CrewAI and Claude paths. The stopped-run writer covers LangGraph only.
- Unit tests that run a backend without `workspace_dir`, and `run_demo` without `PROJECT_WORKSPACE_DIR`, still write into `./workspace/` (the audit's hard-coded-workspace item).
- Strands and Microsoft Agent Framework: still not running.

## 5. Verified

2026-10-07, on the branch head: `pytest tests/unit tests/conformance` 1,818 passed; `pytest tests/integration` 63 passed, 64 skipped; `ruff check` and `ruff format --check` clean; `mypy src/` clean (`mypy evals/` clean on 2026-10-01). Run with the project venv on `PATH`; on a bare `/usr/bin/python` ten gate and smoke tests fail for environment reasons.

## 6. Next

1. Merge into `main`; CI green.
2. **Batch A:** `uv run python scripts/run_smoke_batch.py --n 30 --backends langgraph --team smoke` (the Sep 18 batch cost $0.90 and ran 7.3 hours). Done when every timeout has a `state.json` with `stopped_by` and `stopped_in`.
3. **Read before fixing:** list where the timeouts stopped, split their tokens with `scripts/role_cost.py --batch`, and write the cause down. Then one fix, with a test that fails on the old code.
4. **Batch B:** same command, team and brief. Compare B with A (same instrument), never with September. Report n and both intervals, whichever way it goes.
5. Leave `eval-methodology-alignment` Phase 1 unchecked until its own definition of done is true.

## 7. Open questions

- **Do weeks 1 and 3 of the course still teach the right labs?** Neither has had a stranger run since these changes. Run `/test-course` on both before the next course push.
- **Are dollar shares in `role_cost.py` too easy to quote as a provider invoice?** The report labels them as a token share of the run total; any write-up that drops that clause is quoting a different number.
