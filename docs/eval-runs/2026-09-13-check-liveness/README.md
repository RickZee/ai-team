# Check liveness — what the eval suite can actually see

**Date:** 2026-09-13
**Cost:** $0.00 — no model calls, no network, no new runs
**Tool:** `uv run python -m evals.cli coverage liveness` / `coverage signals`
**Spec:** [`.kiro/specs/eval-coverage/`](../../../.kiro/specs/eval-coverage/README.md)

This is a **measurement of the instruments**, not of `ai-team`. It answers one question per
check: over this corpus, did you ever decide anything? Nothing here is a pass rate and nothing
here is a claim about system quality.

Companion to
[`2026-09-13-langgraph-smoke`](../2026-09-13-langgraph-smoke/README.md) (the run that motivated
it) and the
[eval-methodology audit](../../journal/2026-09-13-eval-methodology-audit.md) (which fixes the
corpus, a different defect).

---

## Headline

Folded from the committed Tier A report
`evals/results/tierA_4671d49ae035_eb36475d7c/report.json`, taxonomy `1.2.0`:

> **20 checks, 8 live, 11 thin, 0 blind, 1 unreachable over 72 traces
> [`FIXTURE-ONLY` · `NON-REPRESENTATIVE` · `EVIDENCE-STARVED`, na 76%]**

Same suite, run against the 50 real traces in `evals/traces/`:

> **20 checks, 0 live, 0 thin, 19 blind, 1 unreachable over 50 traces
> [`CORPUS` · `NON-REPRESENTATIVE` · `EVIDENCE-STARVED`, na 95%]**

The published headline for that same report is `FAIL — 182 failed check(s) across suite`. It is
accurate and it omits that **1435 of 1880 results (76.3%) were `not_applicable`**, because
`not_applicable` appears in no headline, no verdict, no scorecard cell and no incidence row. The
renderer has no field for it.

Full tables: [`liveness-fixtures-1.2.0.md`](./liveness-fixtures-1.2.0.md),
[`signals.md`](./signals.md).

---

## Four findings

### 1. Eleven checks are decided by one fixture pair

`CHK-acceptance-monotonic`, `CHK-constraint-survival`, `CHK-evaluator-capitulation`,
`CHK-gate-env-fidelity`, `CHK-guardrail-fp-budget`, `CHK-hallucination-density`,
`CHK-lesson-effectiveness`, `CHK-metric-source-agreement`, `CHK-premature-termination`,
`CHK-verifier-independence`, `CHK-workspace-isolation` — each `1 pass / 1 fail` or `2 / 2`,
abstaining on 96–98% of the corpus.

A check exercised by exactly the two fixtures written to exercise it is a unit test wearing a
measurement's clothes. It belongs in `tests/`, and while it sits in a coverage table it reads
identically to `CHK-listener-self-trigger` at 10% abstention.

### 2. Two span types are unreachable — no corpus can fix them

| Span type | Read by | Parser |
| --- | --- | --- |
| `human_interrupt` | `CHK-interrupt-latency` (FM-003) | **none** |
| `error` | `CHK-provider-error-rate` (FM-009), `CHK-premature-termination` (FM-015) | **none** |

The literals appear only in `models.py`'s `SpanType` union. `builder.py` maps an `"error"`
*status* to `failed`; that is not a span.

`CHK-interrupt-latency` is therefore **blind by construction on every corpus that will ever
exist**, which is a code defect, not a data state — hence its own verdict, `unreachable`, ranked
above `blind`. `CHK-provider-error-rate` survives because it reads `error`, `llm_call` **or**
`retry`, and the latter two are producible.

The LangGraph smoke run of the same day ended in `interrupt()` → `human_review`. FM-003's check
returns `not_applicable` on it.

### 3. Five span types are parsed and read by nobody

`qa_verdict`, `regression_check`, `session_start`, `subagent_start`, `subagent_stop`. No file in
`evals/` outside `evals/trace/` mentions any of them.

The sharpest case: `CHK-evaluator-capitulation` (FM-017) needs QA verdicts.
`parse_qa_verdicts_jsonl` already turns them into typed `qa_verdict` spans. The check ignores
those spans, reads `trace.raw_result["qa_verdicts"]`, and when that is empty **re-parses the
JSONL by hand** (`verification.py:242–261`) — and when the artifact is absent too it abstains,
92 times, while the spans it needed sit in the trace unread.

### 4. The fixture corpus double-counts 22 of its own fixtures

`evals/fixtures/traces/` holds **94 files carrying 72 distinct `trace_id`s**. Twenty-two ids
appear in two files each:

```
CHK-guardrail-fp-budget__pass__fixture      x2
CHK-interrupt-latency__fail__fixture        x2
CHK-spend-ceiling__pass__fixture            x2
… 19 more
```

`tier_a.load_fixture_traces` globs by filename, so both copies are scored.
`TraceStore.write` refuses a duplicate `trace_id` and `rebuild_index` keys on it, so the store
would collapse them to 72.

So the eleven checks in finding 1 that report `2 pass / 2 fail` are really decided by **one pass
fixture and one fail fixture, counted twice**. Tier A's denominators and the trace store disagree
about how big the fixture corpus is, and the report reflects the larger number.

---

## Why abstentions happen — and the one legitimate kind

Top causes, from the fold:

| Reason | Count | Kind |
| --- | ---: | --- |
| `inconclusive: no acceptance artifacts` | 92 | missing artifact |
| `no qa verdicts` | 92 | missing raw key / orphan span |
| `no lessons in trace.raw_result` | 92 | missing raw key |
| `no passes transitions` | 92 | missing raw key |
| `no guardrail_check spans` | 90 | **no producer on the LangGraph path** |
| `no human_interrupt spans` | 90 | **unreachable — no parser** |
| `no phase_start spans` | 64 | no producer (alignment R1) |
| `status=failed; smoke gate only required on complete runs` | 4 | **legitimately out of scope** |
| `listener self-trigger check applies to crewai flows only` | 9 | **legitimately out of scope** |

The last two are the honest `not_applicable`: evidence was present and the trace was genuinely
outside the check. Thirteen abstentions of 1435. That ratio is why `eval-coverage` R3.5 gives
`not_in_scope` its own code — without separating it, the `EVIDENCE-STARVED` stamp would cry wolf
on the small number of correct abstentions.

---

## What this changes

Corrections owed (spec tasks 1.4, 11.5):

- `evals/taxonomy/COVERAGE.md` — *"None — every check-detected FM has a named implementation"* is
  true and is not a coverage claim. Seventeen implementations; one cannot execute on any corpus,
  eleven have decided one fixture pair each.
- `docs/EVAL_METHODOLOGY.md` — needs a liveness table beside its corpus-state table.

## What may and may not be said

**May say:** the eval suite now reports which of its checks can see anything; on the committed
fixture report 8 of 20 are live, 11 thin, 1 unreachable, and over the real 50-trace corpus 19 are
blind; two span types have no producer and five have no consumer.

**Must not say:** any pass rate from either corpus; that FM-003 or FM-005 is covered; that the
suite measures `ai-team`; that 76% abstention is a corpus problem alone — `unreachable` and
`orphan_signal` are code.

## Reproduce

```bash
# Static — needs no corpus, correct on a fresh clone.
uv run python -m evals.cli coverage signals --strict

# Fold a committed report — no checks re-run, $0.
uv run python -m evals.cli coverage liveness \
  --from-report evals/results/tierA_4671d49ae035_eb36475d7c/report.json

# Run the suite over both corpora and compare columns.
uv run python -m evals.cli coverage liveness
```

`signals --strict` exits 1 while any check reads a span type no parser produces. That is the one
gate this work adds; liveness itself is reported and never gates.

## Next

Spec tasks 1.3–1.5 (record and correct), then 2.1–2.4 (`requires` declarations and the
`na_reason` vocabulary), then 6.3 (`CHK-run-record-complete`, the one new check that fires on the
corpus that already exists). Phase 5 — guardrail and interrupt telemetry, which is what actually
unblinds FM-005 and FM-003 — is blocked on `eval-methodology-alignment` Phase 1.
