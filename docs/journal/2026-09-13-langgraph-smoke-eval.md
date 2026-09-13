# 2026-09-13 — LangGraph smoke as the first real eval case

Task 9.1 (`demos/00_smoke_test`, LangGraph, prototype, $25 cap) was supposed
to be a cheap setup validator and a published benchmark receipt. It became
the first live run that is actually worth open-coding.

Handoff (timeline, trace inventory, Husain loop, what not to publish):
[`docs/eval-runs/2026-09-13-langgraph-smoke/README.md`](../eval-runs/2026-09-13-langgraph-smoke/README.md).

## What happened in one sitting

- Bare OpenRouter `deepseek/deepseek-v4-flash`: **1.528 s / $0.0000716**.
- Harness wrote `calc.py` / `test_calc.py` in ~90 s, then
  `testing_subgraph_failed` on `Path must be under workspace: …/ai-team/workspace`
  (the parent tree, not the run dir). Salvage committed the files anyway.
- Behavioral scope then failed relevance 5% / 0% / 9% / 0% against a 15%
  floor. The scorer concatenated the last 12 AI messages (architect ADR +
  fullstack chatter), not the files on disk. In-subgraph retries (3) then
  `retry_development` (graph-level, `retry_count` 3) until HITL.
- `--timeout 900` did not abort: `DemoTimeoutError` is a catchable
  `Exception` and subgraphs wrap `invoke` in `except Exception`. Wall
  **1600 s**, CLI exit **1**, `completed_at` still null, no `costs.jsonl`.
- Workspace nested three levels: QA prompt used unscope `./workspace`.
  Quality gate: pytest exit 5 (`collected 0`) despite root `test_calc.py`.
- Dashboard Home was empty: CLI runs never enter in-memory `GET /api/runs`.

## Why it belongs in the eval story

The [starved-harness audit](2026-09-13-eval-methodology-audit.md) said we had
machinery and no traces. This run is the opposite problem: a live LangGraph
id with logs that are still too thin for `CHK-guardrail-fp-budget` (no
`guardrail_check` spans — fails live only in structlog), and a product
failure the publications already named (FM-005 lexical FP, FM-008 dashboard
omission, FM-010 layout). Those IDs are **hypotheses for axial coding**.
Open coding in `evals.cli annotate` must not be shown them (R3.7).

9.1 stays **unchecked**. This sitting produced a failure receipt, not
`docs/PERFORMANCE.md`.
