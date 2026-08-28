# Spec: `seven-layer-harness`

Kiro-style three-document spec for treating the execution harness as the product of
`ai-team`, not a side effect of three backends. Read in order:

1. **[`requirements.md`](./requirements.md)** — 20 requirements with EARS acceptance
   criteria, the seven-layer map onto `FM-001…010`, new FMs (`FM-011…013`),
   constraints, and non-goals.
2. **[`design.md`](./design.md)** — architecture (`Shared harness → swappable
   orchestrators → taxonomy as the test suite`), data models, ToolBus, three-file
   contract, change receipt, error handling, testing strategy, and sequencing.
3. **[`tasks.md`](./tasks.md)** — 11 phases, ~42 tasks, each with a definition of
   done and requirement traceability.

## The one-line version

Lift tools, verification, pinned context, guardrails, receipts, routing, and
feedback **above** CrewAI / LangGraph / Claude Agent SDK so no backend can bypass
the bus, then instrument every layer against the failure taxonomy we already
measured.

## Why this exists

[choopyplug1's production checklist](https://x.com/choopyplug1/status/2088973320964215253)
and `docs/posts/failure-taxonomy.md` argue the same thing from opposite directions.
The post is the vocabulary and the bar. The taxonomy is the proof that skipping a
layer is not theoretical — it is `FM-001` prose-as-code, `FM-006` tests-green-app-dead,
`FM-007` unbounded spend, `FM-002` 93k-iteration self-trigger.

`ai-team` already has a seven-layer skeleton. This spec closes the gaps the post
names that the taxonomy already keeps hitting. Highest-leverage slice: **pinned
constraints + unified ToolBus**.

## Constraints baked in

| | |
| --- | --- |
| Product shape | Shared harness (the product) → swappable orchestrators (the engines) → taxonomy as the test suite |
| Backends | CrewAI, LangGraph, Claude Agent SDK — none may bypass the bus |
| Taxonomy `layer` | Keep `model` / `framework` / `harness` / `provider` (eval-harness R4). Add `harness_layer`. |
| Eval harness | Do not redo `.kiro/specs/eval-harness`. New checks register there. |
| Docs | `docs/HARNESS.md` is the layer index. `docs/ARCHITECTURE.md` stays backends/flows. |
| Out of scope for v1 | Fine-tuning weights, replacing a backend, SOC2 certification, polishing all seven layers before the next demo |

## Executing this with Cursor

Point the agent at one task at a time:

```
Read .kiro/specs/seven-layer-harness/requirements.md and design.md for context.
Implement task 1.2 from .kiro/specs/seven-layer-harness/tasks.md.
Do not start any other task. Stop when its Definition of done is satisfied
and `uv run ruff check . && uv run mypy src/ && uv run pytest tests/unit/tools tests/unit/memory tests/unit/evals -q` passes.
```

Phases 0–2 are additive (ToolBus + adapters exist beside current tools). **Phase 3
is the cutover** — after it, a backend that calls `write_file` without going through
the bus is a failing test, not a style comment.

## Minimum defensible slice

If the full plan is too long: **Phases 0–3 plus Phase 5.** A ToolBus every backend
must use, draft-commit on writes, and pinned `CONSTRAINTS.md` the summarizer cannot
drop. That is the pair the analysis names as highest leverage. Receipts, routing,
and the closed lessons loop become measurable once those two are in the shared path.

You do not need all seven layers polished to ship a demo. You already shipped demos.
You need all seven **instrumented** before treating any backend as "the one."
