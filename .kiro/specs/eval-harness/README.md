# Spec: `eval-harness`

Kiro-style three-document spec for building a rigorous eval system for `ai-team`.
Read in order:

1. **[`requirements.md`](./requirements.md)** — 16 requirements with EARS acceptance
   criteria (incl. **R16 harness self-test**), the seeded failure taxonomy (FM-001…FM-010),
   constraints, and non-goals.
2. **[`design.md`](./design.md)** — architecture, data models, component design, the
   $5 cost model, error handling, testing strategy (§7), and migration sequencing.
3. **[`tasks.md`](./tasks.md)** — 12 phases, ~47 tasks, each with a definition of done
   and requirement traceability. Phase 11 closes design §7 / R16 test gaps.

## The one-line version

Separate execution from scoring at a **Trace** boundary, derive the eval suite from
the ten failure modes this system has actually exhibited, detect with free
deterministic checks wherever possible, and let a binary LLM judge gate a build only
after it clears TPR ≥ 0.90 / TNR ≥ 0.90 against a held-out split of human labels.

## Constraints baked in

| | |
| --- | --- |
| Location | extends `evals/` in `ai-team`, kept extractable |
| Per-PR spend | **$0.00** (Tier A: replay from committed trace fixtures, judge cache only) |
| Nightly spend | ≤ $2.00 (Tier B) |
| Hard ceiling | $5.00 (Tier C) |
| Judge stack | home-grown, no DeepEval/Braintrust/LangSmith in the critical path |
| Out of scope for v1 | role-specific evals (`docs/EVALS.md` §13), online production evals, multi-annotator |

## Executing this with Cursor

Point the agent at one task at a time:

```
Read .kiro/specs/eval-harness/requirements.md and design.md for context.
Implement task 1.2 from .kiro/specs/eval-harness/tasks.md.
Do not start any other task. Stop when its Definition of done is satisfied
and `uv run ruff check . && uv run mypy evals/ && uv run pytest tests/unit/evals tests/integration/evals` passes.
```

**Harness tests (R16):** unit under `tests/unit/evals/`; integration under
`tests/integration/evals/` (design §7). Never assert live judge quality in pytest.

Phases 1–3 are strictly additive and safe to run unattended. **Phase 5 is human work**
and cannot be delegated — a model labeling its own ground truth makes every number
downstream meaningless.

## Minimum defensible slice

If the full plan is too long: **Phases 0–5 plus Phase 8.** Traces, a taxonomy bound to
deterministic checks, real error analysis, and a report — with no LLM judges at all —
is a coherent eval system. LLM judges without Phase 5 are not.
