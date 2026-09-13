# Design — Eval Coverage and Check Liveness

**Spec ID:** `eval-coverage`
**Requirements:** [`requirements.md`](./requirements.md)
**Created:** 2026-09-13

---

## 1. The idea

An eval system has three layers, and this repo has been measuring only the middle one.

```
  layer                     question it answers          measured today?
  ─────────────────────────────────────────────────────────────────────────
  1. the system             does ai-team work?           no (corpus starved)
  2. the checks             does the check code work?    yes (94 fixtures)
  3. the instruments        can the checks see anything? NOTHING MEASURES THIS
```

Layer 2 is what a green Tier A proves. The repo knows this and says so —
`FIXTURE-ONLY`, `NON-REPRESENTATIVE`, the honest tables in `EVAL_METHODOLOGY.md`. Layer 1 is
what `eval-methodology-alignment` fixes by pointing the corpus at `output/runs/`.

Layer 3 is the gap. **Fixing layer 1 does not fix layer 3**, and this is the load-bearing claim
of this spec. Re-index `output/runs/` tomorrow and `CHK-interrupt-latency` still cannot fire,
because no code anywhere produces a `human_interrupt` span. `CHK-guardrail-fp-budget` still
cannot see a LangGraph guardrail failure, because those decisions reach structlog and stop. The
richest possible corpus does not help a check reading a signal that is never written.

So the deliverable is an **evidence chain** made explicit, end to end, and a report that names
every break in it:

```
  harness writer  →  log file  →  parser  →  span  →  requires  →  check  →  liveness
  telemetry.py       *.jsonl     parsers    typed    declared     runs      reported
       │                                                  │
       └── no writer → no_producer                        └── no parser → unreachable_signal
                                                          no check → orphan_signal
```

Every arrow can break. Today none of the breaks are visible, and the suite reports a verdict
across all of them.

### Why liveness is the first thing to build

It is free, it is offline, it needs no corpus, and it is the only artifact that makes the rest of
the work legible. Without it, "we added six checks" and "we fixed the guardrail telemetry" are
assertions. With it, each one moves a row from `unreachable` to `live` and the table is the
receipt. It is also the cheapest thing in any of the four specs: one module, no spend, no new
dependency, and it re-reads reports that already exist on disk.

---

## 2. Data model

### 2.1 `EvidenceRequirement` (R1)

Declared per check, at registration, as data.

```python
class EvidenceRequirement(BaseModel):
    """What a check reads. Mandatory evidence absent ⇒ not_applicable."""

    span_types: tuple[SpanType, ...] = ()
    span_types_optional: tuple[SpanType, ...] = ()
    artifacts: tuple[str, ...] = ()          # glob/suffix predicates
    raw_result_keys: tuple[str, ...] = ()
    scalars: tuple[str, ...] = ()            # "cost.usd", "duration_s", "status"
    any_of: bool = False                     # True ⇒ one mandatory item suffices

    def is_empty(self) -> bool: ...
```

`any_of` matters for real checks. `CHK-provider-error-rate` reads `error`, `llm_call` **or**
`retry` and decides on whichever is present; `CHK-constraint-survival` needs `phase_start`
specifically. Collapsing both into "requires these span types" would misclassify one of them, so
the flag is part of the declaration rather than a convention.

The decorator gains one keyword and stays backwards compatible in shape:

```python
@check(
    id="CHK-guardrail-fp-budget",
    failure_mode_id="FM-005",
    tier="A",
    requires=EvidenceRequirement(span_types=("guardrail_check",)),
)
def guardrail_fp_budget(trace: Trace) -> CheckResult: ...
```

R1.3 rejects an empty `requires` at registration. That is deliberate: registration-time failure
is loud, and a check that declares nothing is the case this whole spec is about.

### 2.2 `na_reason` vocabulary (R3.5)

`CheckResult` gains `na_reason: NaReason | None` beside its existing prose `evidence_text`. The
prose stays — it is good prose — but it is not aggregable. 1435 abstentions across 20 distinct
sentence templates cannot be counted; five codes can.

```python
NaReason = Literal[
    "missing_span_type",   # a mandatory span type is absent from the trace
    "missing_artifact",    # a required artifact path is absent
    "missing_raw_key",     # raw_result lacks a key the check reads
    "missing_scalar",      # cost/duration/status is null
    "not_in_scope",        # evidence present; this trace is genuinely outside the check
]
```

`not_in_scope` is the one honest `not_applicable`. A run with no UI does not need a UI smoke
probe, and that is not an instrument failure. Separating it from the other four is what keeps the
`EVIDENCE-STARVED` stamp (R11.1) from crying wolf on legitimate abstentions.

### 2.2b Corpus identity (R3.7)

`CoverageReport` counts distinct `trace_id`, and carries `n_files` beside it so a disagreement is
visible rather than silently resolved. The fixture directory is the case that motivates it: 94
files, 72 ids. `tier_a` scores files, the store keys on ids, and the report has been showing the
file count. Counting identities is the correct choice — a duplicated fixture is one piece of
evidence, not two — and showing both is what makes the drift reportable.

### 2.3 `CheckLiveness` and `CoverageReport` (R2)

```python
Liveness = Literal["live", "thin", "blind", "unreachable"]

class CheckLiveness(BaseModel):
    check_id: str
    failure_mode_id: str | None
    tier: CheckTier
    n_pass: int = 0
    n_fail: int = 0
    n_na: int = 0
    n_error: int = 0
    na_reasons: dict[str, int] = {}          # NaReason → count
    na_reason_text_top: list[tuple[str, int]] = []
    liveness: Liveness
    unreachable_signals: tuple[str, ...] = ()  # span types with no parser

    @property
    def n_decided(self) -> int:              # R3.1 — always shown beside a rate
        return self.n_pass + self.n_fail

class CoverageReport(BaseModel):
    corpus_label: str                        # "fixtures" | "corpus" | a path
    corpus_kind: Literal["FIXTURE-ONLY", "CORPUS", "LIVE"]
    n_traces: int
    checks: list[CheckLiveness]
    na_share: float
    evidence_starved: bool                   # R11.1
    top_abstainers: list[tuple[str, int]]
    provenance: Provenance
```

### 2.4 Classification rule (R2.2)

Order matters. `unreachable` is tested first, because a check that is both starved and broken is
a code defect and should be reported as one.

```
if mandatory span type has no parser in the signal chain:  unreachable
elif n_decided == 0:                                       blind
elif n_decided < 10 or n_na / n_total > 0.90:               thin
else:                                                       live
```

`thin` is the verdict that catches the eleven checks decided by one fixture pair. They are not
blind — they returned a `pass` and a `fail` — and calling them `live` is how a 98%-abstention
check ends up in a coverage table looking identical to `CHK-listener-self-trigger` at 10%.

The 10-trace floor is a deliberately low bar chosen to be embarrassing rather than rigorous. It
is not a statistical threshold; `eval-harness` R6 already owns `min_cases` for anything that
gates. It exists so that `1 pass / 1 fail` cannot read as coverage.

### 2.5 `SignalChain` (R4)

Generated statically — from the `requires` declarations plus a hand-maintained producer table —
so it is correct on a fresh clone with an empty trace store.

```python
class SignalRow(BaseModel):
    span_type: SpanType
    harness_writers: tuple[str, ...]     # module paths that write the record
    log_files: tuple[str, ...]
    parsers: tuple[str, ...]             # functions in evals/trace/parsers.py
    consumers: tuple[str, ...]           # check ids whose requires name it
    flags: tuple[SignalFlag, ...]

SignalFlag = Literal["orphan_signal", "unreachable_signal", "no_producer"]
```

The producer table is hand-maintained and that is a real cost — it can drift from the code. The
mitigation is R4.6: the one CI gate in this spec fires when a check's mandatory span type has no
parser. Drift in the *writer* column degrades a report; drift in the *parser* column breaks a
check, and only the second one is worth a gate.

Known initial state (R4.7):

| Span type | Writers | Parser | Consumers | Flags |
| --- | --- | --- | --- | --- |
| `human_interrupt` | — | **none** | `CHK-interrupt-latency` | `unreachable_signal`, `no_producer` |
| `guardrail_check` | `guardrails/*` (structlog only) | `parse_audit_jsonl` (SDK hooks only) | `CHK-guardrail-fp-budget` | `no_producer` (LangGraph path) |
| `qa_verdict` | `harness/qa_verdicts.py` | `parse_qa_verdicts_jsonl` | — | `orphan_signal` |
| `regression_check` | `harness/session_loop.py` | `parse_sessions_jsonl` | — | `orphan_signal` |
| `session_start` | `harness/session_loop.py` | `parse_sessions_jsonl` | — | `orphan_signal` |
| `subagent_start` | SDK hooks | `parse_audit_jsonl` | — | `orphan_signal` |
| `subagent_stop` | SDK hooks | `parse_audit_jsonl` | — | `orphan_signal` |
| `phase_start` / `phase_end` | **prompt only** → `harness/telemetry.py` | `parse_phases_jsonl` | 5 checks | `no_producer` until alignment Phase 1 |

That last row is the alignment spec's R1 and is listed here only to show the chain is complete.
This spec does not implement it.

---

## 3. Components

### 3.1 `evals/coverage.py` — new

Pure functions, no I/O beyond reading traces and reports.

| Function | Purpose |
| --- | --- |
| `evidence_for(check_id)` | the declared `EvidenceRequirement` |
| `classify(counts, unreachable)` | the R2.2 rule, as one testable function |
| `liveness_from_results(results, ...)` | fold `list[CheckResult]` → `list[CheckLiveness]` |
| `liveness_over_corpus(traces)` | run all checks, fold |
| `liveness_from_report(path)` | fold an existing `report.json` — no re-run needed |
| `signal_chain()` | static `SignalChain`, no corpus |
| `render_markdown(report, ...)` | the table, with stamps |
| `render_side_by_side(a, b)` | R2.8 — fixtures vs corpus in one table |

`liveness_from_report` is what makes this immediately useful: the two reports already in
`evals/results/` can be folded into a liveness table before a single new check exists, which is
how the numbers in `requirements.md` were produced.

### 3.2 `evals/cli.py` — extended

```bash
uv run python -m evals.cli coverage liveness           # corpus + fixtures, side by side
uv run python -m evals.cli coverage liveness --from-report evals/results/<id>/report.json
uv run python -m evals.cli coverage signals            # static chain, works on empty repo
```

Both are $0.00 and offline. `liveness` refuses to touch the network under the same
socket-blocking discipline as `tier_a.py`.

### 3.3 `evals/aggregate.py` — extended

- `ScorecardCell`, `FailureModeIncidence` gain `na_count` (R3.2).
- `FailureModeIncidence` is emitted for **every** active FM with a `liveness` field (R3.4),
  replacing today's behavior where 7 of 17 FMs are simply absent from the table.
- `SuiteReport` gains `coverage: CoverageReport`.
- The renderer gains the `EVIDENCE-STARVED` stamp and the R2.5 verdict suppression.

R12.5 is the constraint that keeps this safe: the migration adds fields and changes no verdict.
The regression test asserts all 20 checks' outcomes fixture-by-fixture before and after.

### 3.4 `src/ai_team/harness/telemetry.py` — extended

`eval-methodology-alignment` R1.3 establishes this module as the single telemetry writer. This
spec adds two record families to it rather than creating new writers:

```python
def emit_guardrail_decision(...)  -> None   # R5 → logs/guardrails.jsonl
def emit_interrupt(...)           -> None   # R6 → logs/interrupts.jsonl
def emit_terminal_state(...)      -> None   # R6.4
```

All carry `writer: "harness"` and land under `<run_record>/logs/` per alignment R1.7. **This
spec must not create a second telemetry module**; if alignment Phase 1 has not landed, the tasks
here block on it.

The `scored_text_source` field (R5.3) deserves a note. The smoke run's finding was not "a
guardrail failed" but "the guardrail scored the last 12 AI messages instead of the workspace."
A record saying `decision: fail, score: 0.05, threshold: 0.15` reproduces the symptom. A record
adding `scored_text_source: "last_12_ai_messages"` reproduces the *diagnosis*, and that is the
difference between a detector and an explanation.

### 3.5 New checks (R8)

Six checks, one module each where the layer fits, all Tier A, all offline.

| Check | Reads | Fails when |
| --- | --- | --- |
| `CHK-watchdog-enforced` | `duration_s`, timeout from contract, terminal state | duration > timeout × (1 + tol) **and** terminal state ≠ `watchdog_expired` |
| `CHK-test-collection-nonempty` | test invocation records, artifacts | tests collected 0 while source + test artifacts exist |
| `CHK-run-record-complete` | `run.json` fields via `raw_result`, `cost` | `completed_at` null, or no cost record on a run that made LLM calls |
| `CHK-write-path-scope` | `tool_result` spans, artifact paths | a committed path repeats the workspace-root segment |
| `CHK-no-rewind-after-artifact` | `phase_start`, `phase_end`, artifacts | a phase re-entered after its output contract was already satisfied |
| `CHK-overhead-ratio` | `duration_s`, control-arm baseline | ratio > contract ceiling; `not_applicable` with no control |

`CHK-no-rewind-after-artifact` is the one with real design risk. "Output contract already
satisfied" is a judgment, and encoding it wrongly produces false positives on legitimate
iteration — a developer phase re-entered because the tests genuinely failed is correct behavior,
not FM-023. The v1 rule is deliberately narrow: fail only when the re-entry was triggered by a
**guardrail** error whose phase differs from the phase being re-entered, which is exactly the
`route_after_testing` → `retry_development` mapping the smoke run hit. Broader definitions wait
for open-coding evidence.

### 3.6 Taxonomy (R9)

`failure_modes.yaml` gains, per new mode:

```yaml
  - id: FM-019
    slug: watchdog_not_enforced
    origin: hypothesis
    hypothesis_evidence:
      runs: ["2026-09-13_182650_write-a-single-python-module_01"]
      documents: ["docs/eval-runs/2026-09-13-langgraph-smoke/README.md"]
    detection: check
    implemented_by: [CHK-watchdog-enforced]
    status: active
```

`loader.py` gains the `hypothesis` origin and excludes those modes from active coverage counts
and origin shares (R9.3). `COVERAGE.md` grows an origin column and a liveness column, which
together answer the question the current file cannot: not "does this FM have a check" but "has
that check ever decided anything, and where did the FM come from."

---

## 4. Resolving the orphan signals (R7)

A decision per span type, recorded here as R7.5 requires.

| Span type | Decision | Reason |
| --- | --- | --- |
| `qa_verdict` | **consume** — re-point `CHK-evaluator-capitulation` | The check needs precisely this signal and currently hand-re-parses the file the parser already typed. Deleting `verification.py:242–261` removes a second JSON parser and a second failure path. |
| `subagent_start` / `subagent_stop` | **consume** — new `CHK-subagent-fanout-bounded` | Unbounded or orphaned subagents are a real harness failure on the SDK backend, and the spans already exist. Cheap. |
| `session_start` | **consume** — fold into `CHK-run-record-complete` | Needs no check of its own; it is corroborating evidence for a complete run record. |
| `regression_check` | **remove parser** | Nothing in the taxonomy is about regression checks, the session loop that writes it is behind a flag, and inventing an FM to justify an existing parser is the tail wagging the dog. Re-add with a consumer if a mode ever needs it. |

Four orphans consumed, one parser deleted. The general rule this encodes: a parser earns its
place by having a reader, and the fix for "no reader" is sometimes deletion.

---

## 5. Error handling

| Condition | Behavior |
| --- | --- |
| Check raises during liveness | record `outcome: error`, continue; `n_error` is reported and never folded into `n_decided` — per `EVAL_METHODOLOGY.md` §6, errors are not failures |
| Trace fails to load | skip, count in `n_unloadable`, name the ids |
| Empty trace store | valid: `n_traces: 0`, every check `blind`, `EVIDENCE-STARVED` set |
| Producer table names a module that no longer exists | warn in the report; do not fail |
| `--from-report` given a schema the code predates | refuse with the schema versions; never guess |
| Telemetry write fails (R5/R6) | warn on the run, continue — alignment R1.4, unchanged |

---

## 6. Testing strategy (R12)

| Target | Test |
| --- | --- |
| Classification | table-driven over all four verdicts and both boundaries (`n_decided == 10`, `na == 0.90`) |
| Mandatory-evidence contract | for each of 20 checks: strip mandatory evidence ⇒ `not_applicable` + correct `na_reason` (R1.5) |
| Empty `requires` | registration raises |
| No-verdict-change | all 20 checks, all 94 fixtures, outcome-identical before/after migration (R12.5) |
| Purity | socket-blocked, per `test_check_purity.py` |
| Signal chain on empty repo | no trace store, full table (R12.6) |
| Stamp threshold | 49.9% / 50.1% `na` share |
| New checks | `pass` / `fail` / `not_applicable` fixture each (R12.3) |
| Hygiene | `tmp_path` only; a test asserts no writes under `evals/` tracked dirs (R12.1) |

---

## 7. Phasing and dependency

```
  Phase 1  liveness over existing reports        ← free, no deps, do this first
  Phase 2  requires declarations + na_reason     ← no deps
  Phase 3  signal chain + the one CI gate        ← needs Phase 2
  Phase 4  report integration + stamps           ← needs Phase 2
  Phase 5  guardrail + interrupt telemetry       ← BLOCKED on alignment Phase 1
  Phase 6  six hypothesis FMs + checks           ← needs Phase 2; Phase 5 for FM-005/003 to go live
  Phase 7  orphan resolution                     ← needs Phase 2
  Phase 8  efficiency / control arm              ← needs harness-alignment arms; spends ≤$1
```

Phase 1 is worth isolating because it delivers the spec's core finding with no code changes to
anything that runs in CI, and because its output is what justifies Phases 2–8 to a reader who
does not already believe the problem exists.

Phase 5 is the only hard cross-spec block. If alignment Phase 1 has not landed,
`emit_guardrail_decision` has no module to live in, and adding one anyway recreates the
scattered-writer problem both specs exist to remove.

---

## 8. Claim discipline (R11)

Three stamps, orthogonal, all renderer-enforced:

| Stamp | Owned by | Means |
| --- | --- | --- |
| `FIXTURE-ONLY` / `CORPUS` / `LIVE` | alignment R15 | what the traces are |
| `NON-REPRESENTATIVE` | alignment R4 | the corpus is too narrow |
| `EVIDENCE-STARVED` | **this spec, R11** | the instruments could not see |

A Tier A run today earns all three, and the current renderer shows one. The sentence this spec
makes available — and the only coverage sentence it authorizes — has the shape:

> Tier A: 20 checks registered, `k` live, `m` thin, `j` blind, `i` unreachable, over `n` traces
> (`FIXTURE-ONLY`, `NON-REPRESENTATIVE`, `EVIDENCE-STARVED`, `na` 76%).

And the sentence it forbids, which `evals/taxonomy/COVERAGE.md` currently implies:

> ~~Every check-detected failure mode has a named implementation.~~

True, and not a coverage claim. Seventeen implementations, two of which cannot execute on any
corpus and eleven of which have decided two fixtures each.

---

## 9. Open decisions

**9.1 — Should `thin` suppress a green verdict, like `unreachable` does (R2.5)?**
Leaning no. `unreachable` is a code defect and deserves to break the shine; `thin` is usually a
corpus problem and alignment already stamps for that. Revisit once the corpus clears its floors —
if checks stay `thin` on a representative corpus, that is an instrument problem after all.

**9.2 — Should the 10-trace `thin` floor be per-check?**
`CHK-workspace-isolation` needs concurrent runs, which are rare by nature, and will look `thin`
forever on an honest corpus. A per-check `expected_applicability` field would fix it and is more
bookkeeping than the problem currently justifies. Deferred.

**9.3 — Does `CHK-overhead-ratio` belong in Tier A at all?**
It needs a control-arm baseline, so on most corpora it returns `not_applicable` — a permanent
`thin` row. Arguably it belongs in the ladder report (`harness-alignment`) rather than the check
suite. Leaning: keep the check, but report overhead in the ladder.

**9.4 — Should `regression_check`'s parser really be deleted (§4)?**
It is the only orphan with no natural consumer, and deletion is cheap to reverse. The risk is
deleting a parser for a signal the session loop starts writing next month. Mitigated by R4.6,
which would flag the reverse case loudly.

**9.5 — Should FM-024 (`harness_overhead_unbounded`) be a failure mode?**
Overhead is a cost, not a failure, and the taxonomy is about failures. Counter-argument: 1000×
the control on a smoke test is a failure of the harness's purpose. Keeping it as
`origin: hypothesis` defers the question honestly — if open coding never produces it as a code,
it becomes `unobserved` and the question answers itself.

**9.6 — `CHK-listener-self-trigger` reads source code, not traces. Does R1.3 reject it?**
As written, yes — its `requires` would be empty, because it inspects
`ai_team.core.flow_wiring` rather than the Trace, and R1.3 rejects an empty declaration at
registration. That is a real tension and the requirement is not wrong to surface it: a check whose
verdict is identical for every trace in the corpus is a static lint, and its per-trace `pass`
count is 94 copies of one fact. Three options, in preference order: (a) add a
`static: true` flag to `EvidenceRequirement` and report such checks in a separate section with
n=1, which is honest about what they measure; (b) move it out of the check registry into a lint;
(c) widen R1.3. Leaning (a) — it keeps the check where it is useful while stopping it from
inflating a coverage table. Resolve before task 2.3.

**9.7 — Should a check that raises on every trace be its own verdict?**
Today it classifies as `blind`, with the error count shown separately. An `erroring` verdict
would be more precise, since the fix is different from both a starved corpus and a missing
parser. Deferred: the current corpus produces no genuine check errors, so the distinction has no
data behind it yet, and inventing a verdict for a case that has never occurred is how the
taxonomy got into trouble in the first place.
