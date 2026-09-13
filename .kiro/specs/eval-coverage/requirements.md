# Requirements — Eval Coverage and Check Liveness

**Spec ID:** `eval-coverage`
**Status:** Draft for implementation
**Owner:** Rick Zakharov
**Target repo:** `ai-team` (extends `evals/checks/`, `evals/trace/parsers.py`, `evals/aggregate.py`,
`src/ai_team/harness/telemetry.py`)
**Created:** 2026-09-13
**Depends on:** [`../eval-harness/`](../eval-harness/) — Trace boundary (R1), check registry (R5),
taxonomy (R5), tiers (R11), provenance (R14). [`../harness-alignment/`](../harness-alignment/) —
FM-014…FM-017. [`../eval-methodology-alignment/`](../eval-methodology-alignment/) — harness-owned
telemetry (R1), FM-018 (R2), corpus source (R5), human open coding (R7), taxonomy provenance (R9),
claim discipline (R15). **None of those are restated here.**

---

## Introduction

`eval-methodology-alignment` fixes the **inputs**: the corpus is built from the wrong tree and
phase telemetry is asked for in a prompt. This spec fixes the **instruments**. They are separate
defects and fixing the first does not fix the second.

An eval suite has two ways to be wrong. It can score the wrong thing — that is the alignment
spec. Or it can score nothing and report a verdict anyway. This repo does the second, and no
artifact it produces says so.

### What the check suite actually decided

Tier A's own most recent report, `evals/results/tierA_4671d49ae035_eb36475d7c/report.json`,
taxonomy `1.2.0`, 20 checks over 94 synthetic fixtures — **1880 check results**:

| Outcome | Count | Share |
| --- | ---: | ---: |
| `not_applicable` | **1435** | **76.3%** |
| `pass` | 263 | 14.0% |
| `fail` | 182 | 9.7% |

The headline reads `FAIL — 182 failed check(s) across suite`. It does not mention that three
quarters of the suite declined to answer. `not_applicable` appears in no headline, no verdict, no
scorecard cell, and no `failure_mode_incidence` row. The renderer has no field for it.

### Eleven of twenty checks are decided by one fixture pair

Per-check outcomes from that same report:

| Check | pass | fail | n/a | n/a share |
| --- | ---: | ---: | ---: | ---: |
| `CHK-acceptance-monotonic` | 1 | 1 | 92 | 98% |
| `CHK-constraint-survival` | 1 | 1 | 92 | 98% |
| `CHK-evaluator-capitulation` | 1 | 1 | 92 | 98% |
| `CHK-hallucination-density` | 1 | 1 | 92 | 98% |
| `CHK-lesson-effectiveness` | 1 | 1 | 92 | 98% |
| `CHK-premature-termination` | 1 | 1 | 92 | 98% |
| `CHK-verifier-independence` | 1 | 1 | 92 | 98% |
| `CHK-gate-env-fidelity` | 2 | 2 | 90 | 96% |
| `CHK-guardrail-fp-budget` | 2 | 2 | 90 | 96% |
| `CHK-interrupt-latency` | 2 | 2 | 90 | 96% |
| `CHK-metric-source-agreement` | 2 | 2 | 90 | 96% |
| `CHK-workspace-isolation` | 2 | 2 | 90 | 96% |
| `CHK-provider-error-rate` | 8 | 2 | 84 | 89% |
| `CHK-tool-call-emitted` | 14 | 5 | 75 | 80% |
| `CHK-draft-commit` | 20 | 1 | 73 | 78% |
| `CHK-phase-repeat-bounded` | 28 | 2 | 64 | 68% |
| `CHK-required-artifacts` | 15 | 65 | 14 | 15% |
| `CHK-spend-ceiling` | 76 | 6 | 12 | 13% |
| `CHK-runtime-smoke-present` | 2 | 82 | 10 | 11% |
| `CHK-listener-self-trigger` | 83 | 2 | 9 | 10% |

A check answering `1 pass / 1 fail` over a 94-trace corpus has been exercised by exactly the two
fixtures written to exercise it — and for the `2 / 2` rows, by **one** pass fixture and **one**
fail fixture counted twice, because 22 of those 94 files share a `trace_id` with another file
(R3.7). It is a unit test wearing a measurement's clothes. And 65 of the
182 headline failures are one check, `CHK-required-artifacts`, firing on fixtures that were never
going to have artifacts.

### On real traces the number is worse and is not reported at all

The 50 traces in `evals/traces/` carry **0 spans, 0 artifacts, and `cost.usd: null`** between
them (`status: failed`, 50 of 50 — see `eval-methodology-alignment` R3). Every check that reads
a span, an artifact, or a cost returns `not_applicable` on every one of them. That is the actual
coverage of this eval system over this project's own history, it is approximately zero, and no
command in the repo prints it.

### Two checks cannot fire on any corpus, ever

This is distinct from a starved corpus. These are breaks in the signal chain:

| Check | FM | Needs | Chain status |
| --- | --- | --- | --- |
| `CHK-interrupt-latency` | FM-003 | `human_interrupt` spans | **No parser in `evals/trace/` emits this span type.** The literal appears only in `models.py`'s `SpanType` union. Unreachable by construction. |
| `CHK-guardrail-fp-budget` | FM-005 | `guardrail_check` spans | Emitted only by `parse_audit_jsonl` from Claude SDK hook events (`parsers.py:296`). LangGraph guardrail decisions go to **structlog only** — `langgraph_guardrail_nodes.py:273` logs `route_after_behavioral`; no `.jsonl` writer exists. |

The 2026-09-13 LangGraph smoke run
([`docs/eval-runs/2026-09-13-langgraph-smoke/`](../../../docs/eval-runs/2026-09-13-langgraph-smoke/README.md))
demonstrates both at once. It ended in a LangGraph `interrupt()` → `human_review`, and it burned
four behavioral-relevance retries at 5%, 0%, 9%, 0% against a 15% floor. Those are textbook
FM-003 and FM-005 events. Both checks would return `not_applicable` on that trace. The run README
already concedes this — *"do not claim CHK-guardrail-fp-budget 'caught' this run"* — which is
honest, and is the honesty doing work that instrumentation should do.

### Five span types are parsed and read by nobody

`evals/trace/parsers.py` builds these spans. No file in `evals/` outside `evals/trace/` mentions
any of them:

| Span type | Producer | Consumer |
| --- | --- | --- |
| `qa_verdict` | `parse_qa_verdicts_jsonl` | **none** |
| `regression_check` | `parse_sessions_jsonl` | **none** |
| `session_start` | `parse_sessions_jsonl` | **none** |
| `subagent_start` | `parse_audit_jsonl` | **none** |
| `subagent_stop` | `parse_audit_jsonl` | **none** |

`qa_verdict` is the sharpest case. `CHK-evaluator-capitulation` (FM-017) needs exactly this
signal, and reads `trace.raw_result["qa_verdicts"]` and then a raw artifact re-parse
(`verification.py:242–261`) — never the spans. So the harness parses the file into typed spans,
the check ignores them and re-parses the file by hand, and when `raw_result` is empty the check
returns `not_applicable` while the spans it needed sit in the trace unread.

### Summary of the gap this spec closes

| Area | Gap today | Requirement |
| --- | --- | --- |
| Check capability | no check declares what evidence it needs | R1 |
| Liveness | nothing reports that a check never fired | R2 |
| `not_applicable` | absent from headline, verdict, scorecard, incidence | R3 |
| Signal chain | no inventory of producer → parser → consumer | R4 |
| FM-005 blindness | guardrail decisions are structlog-only | R5 |
| FM-003 blindness | `human_interrupt` has no producer at all | R6 |
| Orphan signals | 5 span types parsed, 0 consumers | R7 |
| Unmodeled failures | 6 modes visible in the smoke run, no FM | R8 |
| Hypothesis discipline | `origin` has no value for "read from logs, not annotated" | R9 |
| Efficiency | 1600 s vs a 1.528 s control, measured by nothing | R10 |
| Claim discipline | a rate over 76% n/a renders like a rate | R11 |
| Duplicate identities | 94 fixture files, 72 distinct `trace_id`s | R3.7, R3.8 |
| Test hygiene | — | R12 |

---

## R1 — Checks declare the evidence they require

**User story.** As the owner of the check suite, I want every check to state what evidence it
needs in machine-readable form, so that "this check cannot run here" is computable before the
check runs rather than inferred from a prose `not_applicable` string.

### Acceptance criteria

1. The `@check` decorator SHALL accept a `requires` argument holding an `EvidenceRequirement`:
   span types, artifact predicates, `raw_result` keys, and trace scalar fields the check reads.
2. Every one of the 20 registered checks SHALL declare `requires` in a single migration, and the
   declaration SHALL be derived from the check's code, not from its docstring.
3. A check whose `requires` is empty SHALL be rejected at registration time. A check that reads
   nothing cannot decide anything.
4. `EvidenceRequirement` SHALL distinguish **mandatory** evidence (absent ⇒ the check must
   return `not_applicable`) from **optional** evidence (absent ⇒ the check still decides).
5. A test SHALL assert, for every check, that constructing a Trace with all mandatory evidence
   removed yields `not_applicable`, and that the reason string names the missing evidence.
6. `requires` SHALL be data, readable without importing the check body, so that the signal-chain
   report (R4) does not execute check code.

## R2 — Check liveness is computed and reported

**User story.** As a reader of a Tier A report, I want to know which checks actually decided
something, so that a green suite cannot mean an empty one.

### Acceptance criteria

1. The harness SHALL compute, for a given corpus, a `CheckLiveness` record per check holding
   `pass`, `fail`, `not_applicable`, and `error` counts, the `na_reason` histogram, and a
   `liveness` verdict.
2. `liveness` SHALL be one of:
   - `blind` — zero `pass` and zero `fail` over the corpus;
   - `unreachable` — `blind`, and the mandatory evidence has **no producer** in the signal
     chain (R4), so no corpus could change the result;
   - `thin` — decided on fewer than 10 traces, or `not_applicable` on more than 90% of them;
   - `live` — decided on ≥10 traces with ≤90% `not_applicable`.
3. `unreachable` SHALL rank above `blind` in severity, because a starved corpus is a data problem
   and a broken chain is a code problem.
4. `SuiteReport` SHALL carry the liveness table, and the rendered headline SHALL state the count
   of `blind` and `unreachable` checks whenever either is non-zero.
5. A report with any `unreachable` check SHALL NOT render a suite-level verdict of `pass`. It
   SHALL render `pass (instruments incomplete)` with the unreachable check ids named.
6. Liveness SHALL NOT gate CI. It is a state to display, consistent with
   `eval-methodology-alignment` R4.6. The CI job SHALL print the liveness table on every run.
7. `evals.cli` SHALL expose `coverage liveness` computing the table over any trace root at
   **$0.00** with no network access, and SHALL support `--fixtures` to render the fixture corpus
   and the real corpus side by side.
8. The side-by-side view SHALL be the default when both roots are present, because a check that
   is `live` on fixtures and `blind` on the corpus is the exact defect this spec exists to
   surface, and one column cannot show it.

## R3 — `not_applicable` is first-class in every report

**User story.** As a reviewer, I want an abstention counted and shown wherever a pass rate is
shown, so that a denominator cannot quietly shrink to two.

### Acceptance criteria

1. Every rendered rate SHALL show `n_decided` (pass + fail) beside it, and SHALL NOT show a
   percentage computed over a denominator it does not display.
2. `ScorecardCell` and `FailureModeIncidence` SHALL carry `na_count`, and the renderer SHALL
   show it.
3. WHEN a check's `n_decided` is below 10, its rate SHALL render as `n=<k>` with no percentage.
4. `FailureModeIncidence` SHALL be emitted for every active FM, including those with zero
   incidence, with a `liveness` field — so that an FM absent from the table because nothing could
   see it is distinguishable from an FM absent because it did not occur. The 1.2.0 report emits
   incidence rows for 10 of 17 FMs and the other 7 are simply missing.
5. A `not_applicable` result SHALL carry a structured `na_reason` code from a closed vocabulary
   (`missing_span_type`, `missing_artifact`, `missing_raw_key`, `missing_scalar`,
   `not_in_scope`), in addition to its human-readable text.
6. `na_reason` codes SHALL be aggregated per check so that the single most common cause of
   abstention is visible without reading 1435 strings.
7. A corpus SHALL be counted by **distinct `trace_id`**, not by file. `evals/fixtures/traces/`
   holds 94 files carrying **72 distinct ids** — 22 ids appear in two files each, and
   `tier_a.load_fixture_traces` globs by filename, so both copies are scored while
   `TraceStore.write` would refuse the duplicate and `rebuild_index` would collapse them. Every
   `2 pass / 2 fail` row in the current report is therefore **one pass fixture and one fail
   fixture, counted twice**.
8. The report SHALL name `n_files` and `n_distinct_traces` separately whenever they differ, and
   CI SHALL warn WHEN a fixture directory contains two files with the same `trace_id`. Tier A's
   denominators and the trace store SHALL NOT disagree about the size of a corpus.

## R4 — The signal chain is inventoried and gaps are named

**User story.** As a maintainer, I want one table from harness writer to check consumer, so that
a signal nobody reads and a signal nobody writes are both visible.

### Acceptance criteria

1. The harness SHALL emit a `SignalChain` report with one row per span type: the harness module
   that writes the underlying record, the log file, the parser function, and the checks that
   consume it.
2. A row with a parser and no consumer SHALL be flagged `orphan_signal`.
3. A row consumed by a check with no parser SHALL be flagged `unreachable_signal`.
4. A row with a parser but no harness writer SHALL be flagged `no_producer`.
5. The report SHALL be generated by static inspection of `requires` declarations (R1.6) and a
   declared producer table — never by running a corpus, so that it is correct on an empty repo.
6. `coverage signals` SHALL render it, and CI SHALL fail WHEN a new check is registered whose
   mandatory span type has no parser. That is a code defect, not a data state, and it is the one
   thing in this spec that gates.
7. The initial run SHALL record the known state: `human_interrupt` as `unreachable_signal`; five
   span types as `orphan_signal`; `guardrail_check` as `no_producer` for the LangGraph path.

## R5 — Guardrail decisions become harness-owned telemetry

**User story.** As an analyst, I want every guardrail decision in a durable record, so that
FM-005 is detectable on the path where it actually happens.

### Acceptance criteria

1. The harness SHALL write `<run_record>/logs/guardrails.jsonl` from harness code on the
   execution path, with `writer: "harness"` per `eval-methodology-alignment` R1.
2. Each record SHALL carry `run_id`, `backend`, `phase`, `guardrail_id`, `decision`
   (`pass`|`fail`), `score`, `threshold`, `retry_index`, `scored_text_source`, and `timestamp`.
3. `scored_text_source` SHALL name what the guardrail actually read — for the behavioral scope
   guardrail, that it scored the last N AI messages and not the workspace. The smoke run's
   central finding is that the scorer never looks at disk; a record that omits this is not
   evidence of it.
4. All guardrail call sites SHALL write through one module. A guardrail that logs only to
   structlog SHALL be treated as a defect, and `langgraph_guardrail_nodes.py:273`
   (`route_after_behavioral`) SHALL be the first site converted.
5. `parse_guardrails_jsonl` SHALL build `guardrail_check` spans, and
   `CHK-guardrail-fp-budget` SHALL read them without change to its semantics.
6. WHEN the LangGraph smoke run of 2026-09-13 is replayed after this requirement lands, the check
   SHALL return `fail` with the four retry scores as evidence. Until then it SHALL return
   `not_applicable`, and no document SHALL claim otherwise.
7. A guardrail record SHALL be written whether the decision passes or fails. A corpus of failures
   only cannot produce a false-positive rate.

## R6 — Human-interrupt and terminal-state telemetry

**User story.** As an analyst, I want HITL and terminal states recorded, so that a run ending in
`human_review` is visible to the checks rather than only to a human reading `state.json`.

### Acceptance criteria

1. The harness SHALL write `human_interrupt` records — at minimum LangGraph `interrupt()`, CLI
   HITL prompts, and `hitl_source` transitions — to `<run_record>/logs/interrupts.jsonl` with
   `writer: "harness"`.
2. Each record SHALL carry `requested_at`, `resumed_at` or `abandoned_at`, `source`, and the
   graph node or phase that raised it, so that `CHK-interrupt-latency` has a latency to measure.
3. `parse_interrupts_jsonl` SHALL build `human_interrupt` spans, closing the
   `unreachable_signal` flagged in R4.7.
4. The harness SHALL write a terminal-state record naming the run's exit condition
   (`completed`, `failed`, `awaiting_human`, `killed`, `budget_abort`, `watchdog_expired`) and
   whether `finalize()` ran.
5. `CHK-interrupt-latency` SHALL return `not_applicable` — never `pass` — for a run with no
   interrupt records, and the `na_reason` SHALL be `missing_span_type`.

## R7 — Orphan signals earn a consumer or are retired

**User story.** As a maintainer, I want every parsed signal to be read by something, so that
parser code is not maintained for nobody.

### Acceptance criteria

1. Each of the five orphan span types SHALL be resolved in one of two ways: a check reads it, or
   its parser is removed. No span type SHALL remain parsed and unread.
2. `CHK-evaluator-capitulation` SHALL be re-pointed at `qa_verdict` spans as its primary source,
   with the `raw_result` path retained as a fallback and the hand-rolled artifact re-parse in
   `verification.py:242–261` deleted. A check that re-parses a file the parser already typed is
   the bug this requirement removes.
3. `session_start` and `regression_check` SHALL gain a consumer or be removed, and the decision
   SHALL be recorded in the design document with a reason.
4. `subagent_start` / `subagent_stop` SHALL gain a consumer bounding subagent fan-out and
   orphaned subagents, or be removed.
5. Removal SHALL be a deliberate, recorded decision — not the default outcome of nobody choosing.

## R8 — Failure modes observed in the smoke run are modeled

**User story.** As the owner, I want the defects a real run demonstrated to be first-class
failure modes with deterministic checks, so that the next occurrence is caught by the harness
rather than by me reading 1600 seconds of structlog.

### Acceptance criteria

1. The taxonomy SHALL gain six modes, all `origin: hypothesis` (R9), all `detection: check`,
   all Tier A at $0.00:

| ID | Slug | Layer | Check | Evidence from 2026-09-13 |
| --- | --- | --- | --- | --- |
| FM-019 | `watchdog_not_enforced` | harness | `CHK-watchdog-enforced` | `DemoTimeoutError` is a catchable `Exception`; every subgraph wraps `sub.invoke` in `except Exception`; SIGALRM swallowed; wall 1600 s against a 900 s timeout |
| FM-020 | `vacuous_verification` | harness | `CHK-test-collection-nonempty` | quality gate recorded ruff ok + pytest **exit 5**, `collected 0 items`, while `calc.py` and `test_calc.py` existed at the run root |
| FM-021 | `run_record_incomplete` | harness | `CHK-run-record-complete` | `completed_at: null`; no `costs.jsonl`; CLI never calls `ResultsBundle.finalize()` |
| FM-022 | `workspace_path_escape` | harness | `CHK-write-path-scope` | testing subgraph resolved the **parent** `./workspace`; drafts landed in `workspace/<id>/workspace/<id>/workspace/<id>/`, three levels deep, poisoning pytest collection |
| FM-023 | `retry_rewind_after_success` | harness | `CHK-no-rewind-after-artifact` | a testing-phase `GuardrailError` mapped to `retry_development` after `calc.py` and `test_calc.py` were already committed; two nested retry loops, 3×3 |
| FM-024 | `harness_overhead_unbounded` | harness | `CHK-overhead-ratio` | 1600 s harness wall against a 1.528 s / $0.0000716 bare OpenRouter control on the same brief |

2. FM-019's check SHALL fail WHEN a trace's wall duration exceeds its configured timeout by more
   than a tolerance AND no `watchdog_expired` terminal state was recorded — the conjunction is the
   point, since a watchdog that fires correctly is not this failure.
3. FM-020's check SHALL fail on a recorded test invocation that collected zero tests while source
   and test artifacts exist, and SHALL be distinct from FM-006 (`runtime_verification_gap`),
   which is about a smoke probe being absent rather than vacuous.
4. FM-022's check SHALL fail on any committed write path containing a repeated workspace-root
   segment, and SHALL report nesting depth.
5. FM-023's check SHALL fail WHEN a phase is re-entered after a later phase recorded artifacts
   satisfying that phase's output contract. It SHALL be distinct from FM-002
   (`self_triggering_retry_loop`), which bounds repeat count without regard to whether the work
   was already done.
6. FM-024's check SHALL require a recorded control baseline and SHALL return `not_applicable`
   without one. An overhead ratio with no denominator is not a measurement.
7. Every one of the six SHALL ship `pass`, `fail`, and `not_applicable` fixtures, and SHALL be
   scoreable retroactively over the existing corpus.
8. None of these six SHALL be described in any document as observed, confirmed, or prevalent
   until R9's promotion path has run. They are hypotheses with receipts, which is not the same
   as labels.

## R9 — `origin: hypothesis` and the promotion path

**User story.** As a reader of the taxonomy, I want a mode derived from reading logs to be
distinguishable from one derived from open coding, so that axial-coding guesses cannot
accumulate into apparent evidence.

### Acceptance criteria

1. `origin: hypothesis` SHALL be a first-class value alongside `essay`, `reference`, and
   `open_coding` (`eval-methodology-alignment` R9.1), and SHALL mean: derived by a human reading
   run logs, without an unaided open-coding annotation record.
2. A `hypothesis` mode SHALL carry `hypothesis_evidence`: the run ids and document paths it was
   read from — for FM-019…FM-024, the 2026-09-13 smoke run id and its README.
3. `hypothesis` modes SHALL be **excluded from active coverage counts and from taxonomy origin
   shares** in `taxonomy coverage`, and SHALL be reported in their own row.
4. Promotion from `hypothesis` to `open_coding` SHALL require ≥1 annotation record with a
   `trace_id` present in the index, per `eval-methodology-alignment` R9.2. Promotion SHALL NOT be
   available by argument, by a check firing, or by the author's confidence.
5. A `hypothesis` mode whose check fires SHALL NOT be auto-promoted. A check firing is evidence
   the check works; only a human annotation is evidence the mode is real.
6. `taxonomy propose --from-annotations` SHALL surface, after the first open-coding pass, which
   `hypothesis` modes the annotations independently reached — the useful signal being whether
   unaided human coding found the same six.
7. A `hypothesis` mode unconfirmed after two open-coding passes SHALL be marked
   `status: unobserved` per `eval-methodology-alignment` R10.2, not deleted.

## R10 — Harness efficiency is measured against a control

**User story.** As the owner, I want the cost of the harness measured against doing nothing, so
that overhead is a tracked number rather than an anecdote in a handoff note.

### Acceptance criteria

1. The repo SHALL define a **bare-provider control**: the same scenario brief sent as a single
   provider call, recorded with wall time, tokens, and cost.
2. Control runs SHALL be recorded as traces with `arm: "control"`, reusing the arm axis from
   `harness-alignment` R1 rather than adding a parallel concept.
3. `SuiteReport` SHALL render `overhead_ratio` = harness wall ÷ control wall, and
   `cost_ratio`, each with `n` and the control trace id.
4. A single pair SHALL render as `n=1, ANECDOTE` and SHALL NOT be published as a ratio. The
   1600 s / 1.528 s observation is an anecdote and the renderer SHALL say so.
5. Control runs SHALL be capped at **$1.00** total for this spec and SHALL be human-triggered.
6. `CHK-overhead-ratio` SHALL fail only above a configured ceiling, and the ceiling SHALL be
   recorded in the scenario contract rather than hardcoded, because acceptable overhead differs
   per scenario size.
7. No document SHALL state a harness-overhead figure without `n`, the control trace id, and the
   models both sides used.

## R11 — Claim discipline for coverage

**User story.** As a reader of this repo's claims, I want a rate over a mostly-abstaining suite
to look different from a rate over a deciding one, so that 76% `not_applicable` cannot render as
a measurement.

### Acceptance criteria

1. A report WHERE `not_applicable` exceeds 50% of all check results SHALL carry an
   **`EVIDENCE-STARVED`** stamp naming the share and the three checks contributing most
   abstentions.
2. The stamp SHALL be rendered by the report renderer, never asserted in prose — same mechanism
   as `NON-REPRESENTATIVE` (`eval-methodology-alignment` R4.4). The two stamps are orthogonal and
   both SHALL be shown when both apply: one is about the corpus, the other about the instruments.
3. `FIXTURE-ONLY` (`eval-methodology-alignment` R15.1) SHALL be shown together with the
   liveness summary, so that a fixture-corpus result cannot be read as a coverage claim.
4. `docs/EVAL_METHODOLOGY.md` SHALL gain a dated liveness table alongside its corpus-state
   table, and CI SHALL warn WHEN it is more than 30 days older than the newest report.
5. No document, post, badge, or deck SHALL state that a failure mode is *covered* on the strength
   of a registered check. Coverage claims SHALL cite liveness, not registration. The current
   `evals/taxonomy/COVERAGE.md` line *"every check-detected FM has a named implementation"* is
   true and SHALL be qualified with how many of those implementations have ever decided anything.
6. WHERE a check is `unreachable`, every artifact naming its FM as covered SHALL be corrected in
   the same change that discovers it.

## R12 — Test hygiene

**User story.** As a maintainer, I want this spec's additions tested to the standard of the
harness they instrument.

### Acceptance criteria

1. No test SHALL write to `evals/annotations/`, `evals/golden/`, `evals/traces/`, or
   `evals/results/`. Tests SHALL use `tmp_path` roots.
2. Every refusal and classification path added here SHALL reach 100% branch coverage: empty
   `requires` rejection, each of the four `liveness` verdicts, each `na_reason` code, each of the
   three signal-chain flags, the R2.5 verdict suppression, and the `EVIDENCE-STARVED` threshold.
3. Each of the six new checks SHALL have `pass`, `fail`, and `not_applicable` fixtures, matching
   existing convention.
4. A test SHALL assert the liveness computation is pure and offline, under the socket-blocking
   pattern already used by `tests/unit/evals/test_check_purity.py`.
5. A regression test SHALL assert that the 20 pre-existing checks' outcomes are unchanged by the
   `requires` migration, fixture by fixture. This spec adds declarations; it changes no verdicts.
6. A test SHALL assert `coverage signals` is correct with an empty trace store, since R4.5
   requires static generation.

---

## Constraints

| | |
| --- | --- |
| No new package | extends `evals/checks/`, `evals/trace/`, `evals/aggregate.py`, `src/ai_team/harness/` |
| No vendor in the critical path | no Braintrust / LangSmith / Arize / DeepEval; consistent with the other three specs |
| Tier A stays $0.00 | every check added here is deterministic and offline |
| Budget | ≤ **$1.00** for control runs (R10.5). Nothing else in this spec spends. Additive to the $5 suite, $25 ladder, $15 alignment. |
| No semantic changes | the `requires` migration adds declarations and changes no existing check's verdict (R12.5) |
| One gate only | R4.6 — a check whose mandatory span type has no parser fails CI. Liveness itself never gates. |
| Telemetry is harness-owned | R5 and R6 write through harness code on the call path, per `eval-methodology-alignment` R1; no new agent instructions |
| Hypothesis ≠ observed | R8's six modes stay out of active coverage counts until a human annotation promotes them (R9) |
| Out of scope | changing any existing check's semantics, re-opening the arm/ladder design, multi-annotator κ, online monitoring, vendor platforms |

## Non-goals

- Fixing the corpus. That is `eval-methodology-alignment` R5 and this spec depends on it.
- Performing the open coding. That is `eval-methodology-alignment` R7 and is human-only.
- Adding judges. R11 of the alignment spec governs when an FM earns one; nothing here is
  judge-detected.
- Raising the number of checks as a goal in itself. A `blind` check is worse than no check,
  because it produces a row in a table that reads like coverage.
- Proving a framework ranking. Still out of reach, and `harness-alignment` says why.
