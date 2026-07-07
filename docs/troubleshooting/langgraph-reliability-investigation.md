# LangGraph Reliability Investigation — 2026-07-06

Why LangGraph goes 1/5 green on a task the other two backends complete reliably,
based on: the Jul-04 n=5 batch (2× lint-gate kills, 3× `collected 0 items`), the
midday Jul-06 run (4 retry cycles → HITL → approved-over-failure, root-caused to
`from src.calc import` against an empty `src/`), tonight's verification run
(HITL at 21m, gate `passed: false`, `complete_approved`), and source inspection
of the gate and prompts.

## Finding 1 — The dev/QA layout contract exists on only one side (primary)

`config/agents.yaml:169-170` tells **QA**:

> "…are already written in the workspace **src/ directory** by the developer.
> Read them with read_file, then write test files (prefixed test_) using the
> file_writer tool."

The **developer** agents' goals/backstories contain **no file-layout instruction
at all** (verified: no `src/` mention in backend/fullstack developer prompts).
So the developer writes `calc.py` at workspace root or under `src/` depending on
model mood; QA, told sources live in `src/`, imports `from src.calc import …`.
Whenever the developer chose root, pytest collection dies with
`ModuleNotFoundError: No module named 'src.calc'` — the exact failure in 3 of 4
red runs in the n=5 batch and both Jul-06 HITL escalations. Retries don't
converge because neither agent is told the other's convention; the coin gets
re-flipped each retry.

**Fix (small, high yield):**
- Add to both developer prompts: "Write application sources under `src/`
  (e.g. `src/calc.py`) and nothing at workspace root except config. Use
  file_writer."
- Add to QA prompt: "Import modules as `from <name> import …` (workspace root
  and `src/` are both on `sys.path` via conftest)" — or keep `src.`-style but
  then also have the gate's conftest ensure `src/__init__.py` exists.
- Planning phase should pin the layout into **both** downstream prompts (the
  architecture artifact already flows; add a `file_layout` field).

## Finding 2 — Lint gate's autofix misses the class it actually dies on

`graphs/subgraph_runners.py:200` pre-fixes only `--select I,W292`. The midday
failure was **9× W293** (whitespace on blank line) — ruff reports those as
"hidden fixes" requiring `--unsafe-fixes`, so the autofix pass leaves them and
the gate then fails on pure formatting noise. The Jul-04 batch lost 2 runs the
same way, one with 5/5 tests green.

**Fix (one line + one decision):**
- Either run `ruff format .` before `ruff check` (normalizes all whitespace
  classes), or extend the fix pass:
  `ruff check --fix --unsafe-fixes --select I,W291,W292,W293 .`
- Policy question worth settling: should style-only findings fail the gate at
  all? Recommendation: gate = tests + syntax + security; style auto-fixed and
  reported, never fatal. A run with 5/5 passing tests killed by blank-line
  whitespace is a false negative for the comparison.

## Finding 3 — Gate feedback may not be steering retries

The retry loop re-runs development, but both Jul-06 runs burned 3-4 cycles
without fixing the import path, then escalated. The gate's structured result
(`ModuleNotFoundError…`) exists in state, but the repeated identical failures
suggest the retry prompt doesn't lead with it (or the model ignores it).

**Fix:** inject the gate's `tests.output` tail + `reason` verbatim at the TOP of
the retry-development prompt ("Previous attempt failed the quality gate with:
…") and assert in a unit test that the retry prompt contains the last gate
error. Cheap; converts retries from re-rolls into corrections.

## Finding 4 — Metrics stay zero on failing runs (P1-1 residue)

Tonight's `complete_approved` run reported `tasks_completed: 0`,
`files_generated: 0` despite completed planning/dev phases and real files on
disk. The Jul-06 data-integrity work fixed metrics for *passing* runs; the
failing-path population is still missing, which makes red runs look like
no-op runs in the Compare table.

**Fix:** populate tasks/files from phase artifacts regardless of gate outcome;
only `tests_passed/failed` should reflect the gate.

## Finding 5 — LangGraph's profile: fast-or-escalate, and that's fine

Its one green run in the n=5 batch was 1m25s — fastest of any backend, matching
the historical 60-77s baseline. The retry-cap → HITL escalation design works as
intended and surfaces within a minute. The unreliability is **entirely in the
two harness gaps above** (layout contract, lint gate), not in orchestration.
Post-fix expectation: green rate should jump from 1/5 toward CrewAI's level
while keeping the speed advantage. Worth re-running the n=5 batch after Fixes
1-3 to measure exactly that delta — a great before/after story for the posts.

## Side-finding — corrected

An earlier revision of this doc claimed a pytest session deleted the day's
verification run directories. Wrong on both counts: the operator had cleaned
`workspace/`/`output/` manually, and the actual test-hygiene issue ran the
opposite way — LangGraph graph tests invoking `graph.invoke()` directly with
`uuid4()` project ids were *creating* stray ResultsBundle dirs in the real
workspace. That problem was root-caused and fixed the same day (run-identity
contract `run_id ≡ thread_id ≡ project_id`, `RunSession` scoping, post-run
report lifted out of the graph, isolated test harness) — see
[journal/2026-07-06.md](../journal/2026-07-06.md).

## Suggested order

1. Finding 1 (layout contract) + Finding 3 (gate feedback into retries).
2. Finding 2 (lint gate policy).
3. Finding 4 (failing-run metrics).
4. Re-run n=5 batch → record the before/after in comparison results.
