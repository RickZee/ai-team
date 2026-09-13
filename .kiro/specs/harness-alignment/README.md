# Spec: `harness-alignment`

Kiro-style three-document spec for aligning `ai-team` with two published Anthropic
references and turning the comparison into a measurement. Read in order:

1. **[`requirements.md`](./requirements.md)** — 17 requirements with EARS acceptance
   criteria, four new failure modes (FM-014…FM-017), constraints, and non-goals.
2. **[`design.md`](./design.md)** — the arm abstraction, data models, component design,
   the $25 sweep envelope, error handling, testing strategy (§7), claim discipline (§8),
   and five open decisions (§9).
3. **[`tasks.md`](./tasks.md)** — 12 phases, ~47 tasks, each with a definition of done and
   requirement traceability.

Builds on [`../eval-harness/`](../eval-harness/) — the Trace boundary, check registry,
taxonomy, tiers, and provenance all come from there and are not restated here.

## The one-line version

Add an **arm** axis orthogonal to the existing `--backend` axis, so the project can measure
what its harness buys — against a solo agent, against Anthropic's published minimal
harness, and against itself with one component removed at a time — and let every new
detector run free in the $0 Tier A gate.

## Sources

| Source | What it supplies |
| --- | --- |
| [`anthropics/claude-quickstarts/autonomous-coding`](https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding) @3313e97, MIT | The reference arm; the monotonic checklist invariant; the session loop; default-deny bash |
| [Harness Design for Long-Running Application Development](https://www.anthropic.com/engineering/harness-design-long-running-apps) (Rajasekaran, Anthropic Engineering) | The solo control arm; contract negotiation before implementation; context resets over compaction; "context anxiety"; self-evaluation bias |

## Why a ladder rather than a leaderboard

```
  solo  →  harnessed_solo  →  reference  →  ai_team (ablated)  →  ai_team (full)
  nothing  harness, 1 agent   minimal      one component off     all components
```

The README already concedes the three-backend matrix "cannot yet support framework X beats
Y" at n=5 with mixed models. More samples do not fix that — a missing control arm does.
Every rung above runs the same scenario contract, emits the same `Trace`, and is scored by
the same checks, which turns "the harness is the real deliverable" from an assertion into
a number with a confidence interval.

`harnessed_solo` is the rung that makes the ladder answer two questions instead of one:

| Comparison | Isolates |
| --- | --- |
| `solo` → `harnessed_solo` | what the harness buys, holding agent count at one |
| `harnessed_solo` → `ai_team` | what the nine-role decomposition buys, harness fixed |

Without it, `solo → ai_team` confounds harness with decomposition. The nine-agent team is
the most expensive assumption the project makes and currently the only one it never tests.

## Constraints baked in

| | |
| --- | --- |
| Location | extends `evals/` and `src/ai_team/harness/`; no new repo, no fourth backend |
| New checks | all deterministic, **Tier A at $0.00** |
| Sweep budget | ≤ **$25.00** per full ladder sweep, separate from the eval-harness $5 suite; `--dry-run` by default |
| Reference harness | vendored, pinned, **never edited**; adaptations recorded as divergences |
| Claim discipline | `UNDERPOWERED` / `MIXED-MODEL` stamps enforced in the renderer, not the README |
| Default state | Phases 8–10 ship **off by default** until their ablation shows they earn their place |
| Test hygiene | No test may write to tracked ground truth; every refusal path this spec adds reaches 100% branch coverage before its component is enabled (R17) |
| Component staleness | Every ablation result is stamped with the model it was measured on and reported `STALE` when that model is no longer the default — never enforced, only shown |
| Out of scope | framework rankings, gating design-quality judges, multi-annotator labeling, online evals |

## New failure modes

| ID | Slug | Layer | Check |
| --- | --- | --- | --- |
| FM-014 | `acceptance_criteria_mutation` | model | `CHK-acceptance-monotonic` |
| FM-015 | `premature_termination_under_context_pressure` | model | `CHK-premature-termination` |
| FM-016 | `self_graded_verification` | harness | `CHK-verifier-independence` |
| FM-017 | `evaluator_capitulation` | model | `CHK-evaluator-capitulation` |

All four are checkable from a Trace with no model call, and all four can be run
retroactively over the existing corpus (task 2.7) before a single new dollar is spent.

FM-017 is the evaluator that finds a real blocker and then approves the work anyway —
distinct from FM-016, where the evaluator is not independent in the first place, and
distinct from `eval-harness`'s offline judge alignment, which scores traces after the fact
rather than gating a build. Its false-negative rate needs no human labels: every item QA
accepted that a deterministic verifier later failed is a counted miss (R16.4).

## Executing this with Cursor

Point the agent at one task at a time:

```
Read .kiro/specs/harness-alignment/requirements.md and design.md for context.
Implement task 1.2 from .kiro/specs/harness-alignment/tasks.md.
Do not start any other task. Stop when its Definition of done is satisfied and
`uv run ruff check . && uv run mypy src/ evals/ && uv run pytest tests/unit` passes.
```

Phases 0–3 and 6 are free and safe to run unattended. **Phases 4, 5, 7.4 and 11 spend
money** and are human-triggered with explicit ceilings. Phases 8–10 change how a normal run
behaves and must stay behind their flags until measured.

## Minimum defensible slice

**Phases 0–2, plus 4, plus 6.** A protected acceptance list, three new deterministic failure
modes scored retroactively, the `solo` and `harnessed_solo` control arms, and a report that
refuses to overclaim. Phase 8 without Phase 1 is not worth building — resumption without a
durable, protected checklist is just a longer run.

If even that is too long: **task 4.5**. Two live runs plus an existing `ai_team` trace
produce the only number here that could change what you build next.
