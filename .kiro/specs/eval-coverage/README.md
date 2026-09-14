# Spec: `eval-coverage`

Kiro-style three-document spec for making the eval harness report what it **cannot see**. Read in
order:

1. **[`requirements.md`](./requirements.md)** — 12 requirements with EARS acceptance criteria, six
   new failure modes (FM-019…FM-024), constraints, and non-goals.
2. **[`design.md`](./design.md)** — the evidence-chain model, `EvidenceRequirement`, the liveness
   classifier, signal-chain inventory, orphan-signal resolutions (§4), claim discipline (§8), and
   five open decisions (§9).
3. **[`tasks.md`](./tasks.md)** — 8 phases, 38 tasks, each with a definition of done and
   requirement traceability.

Builds on [`../eval-harness/`](../eval-harness/) (Trace boundary, check registry, taxonomy,
tiers), [`../harness-alignment/`](../harness-alignment/) (arms, FM-014…FM-017), and
[`../eval-methodology-alignment/`](../eval-methodology-alignment/) (harness-owned telemetry,
FM-018, corpus source, human open coding, taxonomy provenance, claim discipline). None are
restated.

## The one-line version

`eval-methodology-alignment` fixes the **inputs**. This fixes the **instruments** — because
pointing the corpus at the right tree does not help a check reading a signal no code ever writes,
and today nothing in the repo reports the difference.

## What the audit found

The suite's own most recent report — `evals/results/tierA_4671d49ae035_eb36475d7c/report.json`,
taxonomy 1.2.0, 20 checks over 94 fixtures:

| | |
| --- | ---: |
| check results | 1880 |
| `not_applicable` | **1435 (76.3%)** |
| `pass` | 263 |
| `fail` | 182 |

The headline reads `FAIL — 182 failed check(s) across suite`. It does not mention that three
quarters of the suite declined to answer, because **`not_applicable` appears in no headline, no
verdict, no scorecard cell, and no incidence row.** The renderer has no field for it.

| Finding | Detail |
| --- | --- |
| 11 of 20 checks are decided by one fixture pair | `1 pass / 1 fail` or `2 / 2`, `not_applicable` on 96–98% of the corpus. A unit test wearing a measurement's clothes. |
| 65 of the 182 headline failures are one check | `CHK-required-artifacts`, firing on fixtures that were never going to have artifacts. |
| On the real corpus, coverage is ~zero and unreported | The 50 traces in `evals/traces/` carry **0 spans, 0 artifacts, `cost.usd: null`**. Every span-, artifact- or cost-reading check abstains on all 50. No command prints this. |
| `CHK-interrupt-latency` (FM-003) can never fire | It needs `human_interrupt` spans. **No parser in `evals/trace/` emits that span type** — the literal appears only in the `SpanType` union. Unreachable by construction, on any corpus. |
| `CHK-guardrail-fp-budget` (FM-005) cannot see the LangGraph path | `guardrail_check` spans come only from Claude SDK hook events. LangGraph guardrail decisions reach **structlog and stop** — `langgraph_guardrail_nodes.py:273` logs `route_after_behavioral`; no `.jsonl` writer exists. |
| The fixture corpus double-counts 22 of its own fixtures | `evals/fixtures/traces/` holds **94 files carrying 72 distinct `trace_id`s**. `tier_a` globs by filename and scores both copies; `TraceStore.write` would refuse the duplicate. Every `2 pass / 2 fail` row is one pass fixture and one fail fixture, counted twice. |
| 5 span types are parsed and read by nobody | `qa_verdict`, `regression_check`, `session_start`, `subagent_start`, `subagent_stop` — no file in `evals/` outside `evals/trace/` mentions any of them. |

### The sharpest one

`CHK-evaluator-capitulation` (FM-017) needs QA verdicts. `parse_qa_verdicts_jsonl` already turns
them into typed `qa_verdict` spans. The check ignores those spans, reads
`trace.raw_result["qa_verdicts"]`, and when that is empty **re-parses the JSONL by hand**
(`verification.py:242–261`) — and when the artifact is absent too, abstains, while the spans it
needed sit in the trace unread.

### The run that proves it

The 2026-09-13 LangGraph smoke
([`docs/eval-runs/2026-09-13-langgraph-smoke/`](../../../docs/eval-runs/2026-09-13-langgraph-smoke/README.md))
ended in `interrupt()` → `human_review` after burning four behavioral-relevance retries at
**5%, 0%, 9%, 0%** against a 15% floor. Textbook FM-003 and FM-005. **Both checks would abstain
on that trace.** The run README already concedes it — *"do not claim CHK-guardrail-fp-budget
'caught' this run"* — which is honest, and is honesty doing work that instrumentation should do.

## The three layers

```
  layer              question                      measured today?
  ──────────────────────────────────────────────────────────────────────
  1. the system      does ai-team work?            no — corpus starved
  2. the checks      does the check code work?     yes — 94 fixtures
  3. the instruments can the checks see anything?  NOTHING MEASURES THIS
```

Layer 1 is `eval-methodology-alignment`. Layer 2 is what a green Tier A proves, and the repo says
so with `FIXTURE-ONLY`. Layer 3 is this spec, and the reason it is separate is that **fixing
layer 1 does not fix it**.

## The evidence chain

```
  harness writer  →  log file  →  parser  →  span  →  requires  →  check  →  liveness
  telemetry.py       *.jsonl     parsers    typed    declared     runs      reported
       │                                                  │
       └─ no writer → no_producer                         ├─ no parser → unreachable_signal
                                                          └─ no check  → orphan_signal
```

Every arrow can break. Today none of the breaks are visible and the suite reports a verdict
across all of them.

## Liveness verdicts

| Verdict | Means | Fix is |
| --- | --- | --- |
| `unreachable` | blind, and the evidence has no producer — no corpus could change it | **code** |
| `blind` | zero `pass` and zero `fail` over this corpus | data, usually |
| `thin` | decided on <10 traces, or >90% abstention | data, usually |
| `live` | decided on ≥10 traces with ≤90% abstention | — |

`unreachable` ranks above `blind` on purpose: a starved corpus is a data problem, a broken chain
is a code problem, and only one of them gets better by waiting.

## New failure modes

All six are `origin: hypothesis` — read from run logs by a human, **not** from an unaided
open-coding annotation. They are excluded from active coverage counts until
`eval-methodology-alignment` R7's human pass promotes them, and promotion requires an annotation
record, never an argument and never a check firing.

| ID | Slug | Check | Receipt from 2026-09-13 |
| --- | --- | --- | --- |
| FM-019 | `watchdog_not_enforced` | `CHK-watchdog-enforced` | 1600 s wall against a 900 s timeout; `DemoTimeoutError` is a catchable `Exception` and every subgraph swallows it |
| FM-020 | `vacuous_verification` | `CHK-test-collection-nonempty` | quality gate recorded ruff ok + pytest **exit 5**, `collected 0 items`, with `calc.py` and `test_calc.py` present |
| FM-021 | `run_record_incomplete` | `CHK-run-record-complete` | `completed_at: null`, no `costs.jsonl` — CLI never calls `finalize()` |
| FM-022 | `workspace_path_escape` | `CHK-write-path-scope` | drafts landed three levels deep in `workspace/<id>/workspace/<id>/workspace/<id>/`, poisoning pytest collection |
| FM-023 | `retry_rewind_after_success` | `CHK-no-rewind-after-artifact` | a testing-phase `GuardrailError` mapped to `retry_development` **after** the files were committed; two nested loops, 3×3 |
| FM-024 | `harness_overhead_unbounded` | `CHK-overhead-ratio` | 1600 s against a 1.528 s / $0.0000716 bare provider control on the same brief |

FM-023 is the interesting one, and it is the smoke run's real finding. The files landed in ~90 s.
What burned the next 25 minutes was a relevance scorer reading conversation prose instead of disk,
and a router that rewound development because testing raised a guardrail error. FM-002 bounds how
many times a phase may repeat; it says nothing about whether the work was already done.

## Three stamps, orthogonal

| Stamp | Owned by | Means |
| --- | --- | --- |
| `FIXTURE-ONLY` / `CORPUS` / `LIVE` | alignment R15 | what the traces are |
| `NON-REPRESENTATIVE` | alignment R4 | the corpus is too narrow |
| `EVIDENCE-STARVED` | **this spec, R11** | the instruments could not see |

A Tier A run today earns all three. The renderer shows one.

## Constraints baked in

| | |
| --- | --- |
| Location | extends `evals/checks/`, `evals/trace/`, `evals/aggregate.py`, `src/ai_team/harness/`; no new package |
| No vendor in the critical path | no Braintrust / LangSmith / Arize / DeepEval, consistent with the other three specs |
| Tier A stays $0.00 | every check added here is deterministic and offline |
| Budget | ≤ **$1.00**, control runs only (R10.5). Additive to the $5 suite, $25 ladder, $15 alignment. |
| No semantic changes | the `requires` migration adds declarations and changes **no** existing check's verdict — task 2.5 is the guard |
| Two gates only | a check whose mandatory span type has no parser fails CI (R4.6); eval vocabulary in an agent prompt fails CI (R14.2). Liveness itself never gates. |
| Evals never reach agents | check results, liveness verdicts and FM ids stay out of every agent-facing path (R14.1). Product gate results — pytest, ruff, smoke — are unaffected. |
| Telemetry is harness-owned | R5/R6 write through `harness/telemetry.py` per alignment R1 — **not a second writer** |
| Hypothesis ≠ observed | FM-019…FM-024 stay out of active coverage counts until a human annotation promotes them |
| Out of scope | changing existing check semantics, re-opening the arm/ladder design, multi-annotator κ, online monitoring |

## What a run may learn from an eval

Per-run check evidence (R13) makes an automated feedback loop tempting, and R14 draws the line:

```
  PRODUCT LOOP   run → pytest / ruff / smoke → agent context → next attempt        (unchanged)
  EVAL LOOP      run → reports/check_results.json → human → harness fix → replay
  CORPUS LOOP    coverage → cells "never measured" → which scenarios run next      (the one automation)
```

An eval verdict in an agent's context turns the measurement into a target, and this taxonomy
already has three modes for that: FM-014 (mutates the definition of done), FM-016 (writer is also
the passer), FM-018 (reports its own work). The corpus loop is safe because it changes the
sampling, not the subject — the contract handed to an agent is byte-identical either way.

## On fidelity to the source material

The methodology in `eval-methodology-alignment` R7–R15 is Husain and Shankar's: ~100-trace pool,
≥30 unaided, saturation, benevolent dictator, binary verdicts, 100–200 labels per judged mode,
TPR/TNR never accuracy, generic metrics as a sampling signal only, 2–4 week cadence.

**Instrument liveness is not theirs.** They write about LLM application traces, where the trace
*is* the model input and output and exists by construction. In an agentic harness the telemetry is
something the harness must write, so "the check cannot see anything" is a failure mode their
setting does not produce. This spec is an extension for this domain, not an implementation of
something in the article, and it should not borrow the authority.

Two acknowledged gaps: **multi-annotator agreement** (they discuss κ between humans; this repo
declines it for the single dictator — a deliberate deviation, not coverage), and **"evals as living
requirements"** (nothing here re-derives a requirement from a confirmed failure mode; design
decision §9.8).

## Cross-spec dependency

**Phase 5 is blocked** on `eval-methodology-alignment` Phase 1, which creates
`src/ai_team/harness/telemetry.py`. The guardrail and interrupt writers belong in that module. If
Phase 1 has not landed, the correct action is to stop — adding a second telemetry writer here
recreates the scattered-writer defect both specs exist to remove.

Everything else is independent and free.

## Minimum defensible slice

**Phase 1, plus tasks 2.1–2.4, plus 6.3.** Liveness measured and published, every check declaring
what it reads, and one new check (`CHK-run-record-complete`) that fires on the corpus that already
exists. That turns "20 checks registered, 17 failure modes covered" into a number that means
something.

If even that is too long: **tasks 1.3 and 1.4** — publish the liveness table and correct the
claims it invalidates. No code, and it removes the most misleading sentence the repo currently
ships:

> `evals/taxonomy/COVERAGE.md`: *"None — every check-detected FM has a named implementation."*

True. Seventeen implementations, two of which cannot execute on any corpus, eleven of which have
decided two fixtures each.

## Executing this with Cursor

```
Read .kiro/specs/eval-coverage/requirements.md and design.md for context.
Implement task 2.1 from .kiro/specs/eval-coverage/tasks.md.
Do not start any other task. Stop when its Definition of done is satisfied and
`uv run ruff check . && uv run mypy src/ evals/ && uv run pytest tests/unit` passes.
```

Phases 1–4, 6 and 7 are free and safe to run unattended. **Phase 5 is blocked** on the alignment
spec. **Phase 8 spends** (≤$1.00) and is human-triggered. **Task 6.9 wires the promotion path but
must not exercise it** — promotion needs the human annotation pass, which is alignment Phase 4 and
is not delegable.
