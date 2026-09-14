# Implementation Plan — Eval Coverage and Check Liveness

**Spec ID:** `eval-coverage`
**Requirements:** [`requirements.md`](./requirements.md) · **Design:** [`design.md`](./design.md)

11 phases, 54 tasks. Phase 1 tasks 1.1–1.2 and all of Phase 1b are **done** (shipped 2026-09-13/14:
`evals/coverage.py`, `evals/ui/workbench.html`, `annotate bundle`); everything else is
unexecuted.

---

## How to execute this plan

- Work **one task at a time, in order**. Do not batch phases.
- Every task lists a **Definition of done**. Do not mark it complete until each bullet is
  literally true.
- Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run mypy evals/ && uv run pytest tests/unit`
  before marking any task complete.
- **Nothing in Phases 1–7 spends money.** Phase 8 spends ≤ $1.00 and is human-triggered.
- **Phase 5 is blocked** on `eval-methodology-alignment` Phase 1 (`harness/telemetry.py`). Do not
  work around the block by creating a second telemetry writer — that is the defect both specs
  remove. If Phase 1 has not landed, stop and say so.
- No task in this plan may change an existing check's verdict. Task 2.5 is the guard.

Cursor prompt shape:

```
Read .kiro/specs/eval-coverage/requirements.md and design.md for context.
Implement task 2.1 from .kiro/specs/eval-coverage/tasks.md.
Do not start any other task. Stop when its Definition of done is satisfied and
`uv run ruff check . && uv run mypy src/ evals/ && uv run pytest tests/unit` passes.
```

---

## Phase 1 — Liveness over what is already on disk (free, no dependencies)

- [x] **1.1 `evals/coverage.py` — liveness folding and renderers**
  - `Liveness`, `CheckLiveness`, `CoverageReport`, `classify()`,
    `liveness_from_results()`, `liveness_from_report()`, `liveness_over_corpus()`,
    `signal_chain()`, `render_markdown()`, `render_side_by_side()`.
  - Offline, pure, no new dependency.
  - **Definition of done:** module imports with no network; `classify` covers all four verdicts;
    `liveness_from_report` folds `evals/results/*/report.json` without re-running checks.
  - _Requirements: R2.1, R2.2, R2.7, R4.5, R11.1_

- [x] **1.2 `coverage liveness` / `coverage signals` CLI**
  - Subcommands with `--traces-root`, `--from-report`, `--fixtures`, `--json`, `--out`.
  - **Definition of done:** both run at $0.00 with sockets blocked; `signals` works with an empty
    trace store.
  - _Requirements: R2.7, R2.8, R4.6, R12.6_

- [x] **1.3 Record the baseline liveness artifact**
  - `docs/eval-runs/2026-09-13-check-liveness/README.md` — the fixture-vs-corpus table, the
    1435/1880 abstention split, the two unreachable checks, the five orphan signals. Corpus kind
    stamped; no rate without `n`.
  - **Definition of done:** table reproduces from `coverage liveness --from-report`; every figure
    traceable to a committed report.json; no claim of a pass rate.
  - _Requirements: R11.1, R11.3, R11.5_

- [ ] **1.4 Correct the coverage claims this finding invalidates**
  - `evals/taxonomy/COVERAGE.md` — add `origin` and `liveness` columns; qualify
    *"every check-detected FM has a named implementation."*
  - `docs/EVAL_METHODOLOGY.md` — dated liveness table beside the corpus-state table.
  - **Definition of done:** no document states an FM is covered on the strength of registration
    alone; both files name the two unreachable checks.
  - _Requirements: R11.4, R11.5, R11.6_

- [x] **1.5 Journal entry**
  - [`docs/journal/2026-09-14-check-liveness.md`](../../../docs/journal/2026-09-14-check-liveness.md)
    — the findings, what was built, what did not change, the live next-steps list, and the
    open questions. `docs/journal/README.md` index row and a `journey.md` chapter added.
  - Dated the 14th, not the 13th: the sitting ran past midnight and the handoff chain is
    dated by when it was written, never by when the work started.
  - _Requirements: R11.4_

## Phase 1b — The annotation workbench (R13 of eval-methodology-alignment)

Shipped 2026-09-13/14. This phase exists because `eval-methodology-alignment` R13 names
annotation friction as the reason open coding never happened, and R8.3 requires a human
accept/merge/reject surface between the clusterer and the taxonomy that did not exist anywhere.

- [x] **1b.1 `evals/ui/workbench.html` — four stages, gated in the loop's order**
  - Stage 1 open coding (keyboard-driven, no `$EDITOR`), stage 2 axial coding
    (accept/rename/reject + Wilson intervals), stage 3 taxonomy YAML draft, stage 4 judge gate.
  - Self-contained: no dependency, no network, no build step, opens from `file://`.
  - **Definition of done:** stage 1 surfaces no model output and no taxonomy vocabulary; gates
    lock at 30 unaided records, ≥1 accepted category, and 100 labels respectively; a locked
    stage states what it is waiting for.
  - _Requirements: alignment R7.3, R7.4, R7.5, R8.1, R8.3, R8.4, R9.2, R11.1, R12.3, R13.1–R13.5_

- [x] **1b.2 `annotate bundle` — export a sample for the page**
  - `--skip-annotated` resumes a sitting; missing traces are recorded, never fatal.
  - **Definition of done:** bundling the existing real sample yields 50 traces, 0 missing.
  - _Requirements: alignment R13.3_

- [x] **1b.3 Export ingests through the command that already exists**
  - The page's JSONL matches `run_batch_annotate`'s accepted shape, so
    `annotate --sample <id> --batch-file <file>` ingests it with no new code.
  - **Definition of done:** round trip verified end to end into a temp annotations root,
    producing valid `AnnotationRecord` lines with `saturation_streak` computed.
  - _Requirements: alignment R7.1, R13.1_

- [x] **1b.4 Mirror parity with the Python originals**
  - `normalizeTag` / `wilson` / `saturationStreak` verified against
    `propose.normalize_tag`, `reliability.wilson_ci`, `annotate.saturation_streak`.
  - **Definition of done:** identical on 20 normalisation cases, Wilson to 6 decimal places,
    saturation across 7 sequences; pinned in `test_annotate_bundle.py` so drift fails a test.
  - _Requirements: R12.5_

- [x] **1b.5 Headless render smoke test**
  - `tests/unit/evals/workbench/smoke.js` + `test_workbench_smoke.py`; 23 assertions over a
    fixture bundle mixing traces with and without spans. Skips without node.
  - **Definition of done:** asserts the refusal paths, both card shapes, all four gates, and
    that no FM id or taxonomy slug is embedded in the page.
  - _Requirements: R12.2, R12.4_

- [ ] **1b.6 Decide whether the node smoke test joins CI**
  - The repo already has node for the frontend. Not wired in — a deliberate open question, not
    an oversight.
  - _Requirements: R12.4_

- [ ] **1b.7 Carry `unaided` into `AnnotationRecord`**
  - The page emits it and the ingest path currently drops it, because the field does not exist
    yet. It is alignment R7.4, and until it lands the unaided count is inferred rather than
    recorded.
  - **Definition of done:** `AnnotationRecord.unaided` exists; `apply_batch_item` preserves it;
    `taxonomy propose` counts it rather than assuming.
  - _Requirements: alignment R7.4_

## Phase 2 — Evidence declarations

- [ ] **2.1 `EvidenceRequirement` model**
  - In `evals/checks/base.py`; `span_types`, `span_types_optional`, `artifacts`,
    `raw_result_keys`, `scalars`, `any_of`, `is_empty()`.
  - **Definition of done:** typed, mypy-clean, importable without importing check bodies.
  - _Requirements: R1.1, R1.4, R1.6_

- [ ] **2.2 `@check(requires=...)` with empty-rejection**
  - Decorator accepts and stores `requires`; raises at registration when `is_empty()`.
  - **Definition of done:** a test asserts registration of a `requires`-less check raises.
  - _Requirements: R1.1, R1.3_

- [ ] **2.3 Declare `requires` for all 20 existing checks**
  - Derived from each check's code, not its docstring. Cross-check against the observed
    `not_applicable` reasons in the 1.2.0 report.
  - **Definition of done:** all 20 declare; `any_of` set on `CHK-provider-error-rate`; no
    declaration contradicts the check body.
  - _Requirements: R1.2, R1.4_

- [ ] **2.4 `NaReason` vocabulary on `CheckResult`**
  - Five codes; `na()` helper takes the code; all 20 checks pass one.
  - **Definition of done:** every `na()` call site supplies a code; `not_in_scope` used only where
    evidence is present and the trace is genuinely out of scope.
  - _Requirements: R3.5, R3.6_

- [ ] **2.5 No-verdict-change regression test**
  - Snapshot all 20 checks × 94 fixtures before the migration; assert outcome-identical after.
  - **Definition of done:** test fails if any outcome changes; snapshot committed under
    `tests/unit/evals/`, not `evals/`.
  - _Requirements: R12.1, R12.5_

- [ ] **2.6 Mandatory-evidence contract test**
  - For each check: strip mandatory evidence ⇒ `not_applicable` with the matching `na_reason`.
  - **Definition of done:** 20 parametrized cases; each asserts code and that the text names the
    missing evidence.
  - _Requirements: R1.5, R12.2_

## Phase 3 — Signal chain and the parser gate

- [ ] **3.1 Producer table**
  - `evals/trace/producers.py` — span type → harness writer modules → log files. Hand-maintained,
    documented as such.
  - **Definition of done:** every `SpanType` has a row; missing writers recorded as `—`, not
    guessed.
  - _Requirements: R4.1, R4.4_

- [ ] **3.2 `signal_chain()` static generation**
  - Joins producer table, parser inventory, and `requires` consumers. Flags `orphan_signal`,
    `unreachable_signal`, `no_producer`.
  - **Definition of done:** correct with an empty trace store; reproduces the R4.7 known state
    exactly.
  - _Requirements: R4.1–R4.5, R4.7_

- [ ] **3.3 CI gate: mandatory span type with no parser**
  - Fails the build when a registered check's mandatory span type has no parser.
  - **Definition of done:** gate fails on a deliberately broken check in a test; passes on the
    current registry **after** Phase 6 lands `human_interrupt`'s parser, and until then is
    allow-listed with `CHK-interrupt-latency` named and dated in the allow-list.
  - _Requirements: R4.6_

- [ ] **3.4 `coverage signals` renders the chain**
  - Markdown + JSON.
  - _Requirements: R4.6, R12.6_

## Phase 4 — Reports tell the truth

- [ ] **4.1 `na_count` on `ScorecardCell` and `FailureModeIncidence`**
  - _Requirements: R3.2_

- [ ] **4.2 Emit incidence for every active FM with a `liveness` field**
  - Replaces today's behavior where 7 of 17 FMs are absent from the table.
  - **Definition of done:** the 1.2.0 corpus produces 17 rows, not 10; an FM with no incidence is
    distinguishable from an FM nothing could see.
  - _Requirements: R3.4_

- [ ] **4.3 `n_decided` beside every rate; suppress percentages under 10**
  - **Definition of done:** no rendered percentage without its displayed denominator.
  - _Requirements: R3.1, R3.3_

- [ ] **4.3b Count corpora by distinct `trace_id`; report `n_files` beside it**
  - Warn when a fixture directory holds two files sharing a `trace_id`.
  - **Definition of done:** the 22 duplicated fixture ids are named; Tier A denominators and
    `TraceStore.rebuild_index` agree on corpus size; every `2 pass / 2 fail` row resolves to
    `1 / 1`.
  - _Requirements: R3.7, R3.8_

- [ ] **4.4 `SuiteReport.coverage` + `EVIDENCE-STARVED` stamp**
  - Threshold 50% of all results, excluding `not_in_scope`. Names the top three abstainers.
  - **Definition of done:** renderer-enforced; boundary tested at 49.9% / 50.1%.
  - _Requirements: R11.1, R11.2, R12.2_

- [ ] **4.5 Headline names blind/unreachable counts; verdict suppression**
  - `pass (instruments incomplete)` when any check is `unreachable`.
  - **Definition of done:** a suite with one unreachable check cannot render a bare `pass`.
  - _Requirements: R2.4, R2.5_

- [ ] **4.6 CI prints the liveness table every run; never gates on it**
  - _Requirements: R2.6_

## Phase 4c — Per-run check evidence (R13)

- [ ] **4c.1 Write `<run_record>/reports/check_results.json`**
  - Harness-owned, `writer: "harness"`, one entry per Tier A check with `na_reason`.
  - **Definition of done:** a failed write warns and the run completes; no file when no checks are
    registered.
  - _Requirements: R13.1, R13.2, R13.6_

- [ ] **4c.2 Render it as evidence, not a score**
  - **Definition of done:** no pass rate, percentage or ratio anywhere in the per-run view; pass
    counts always shown beside abstention counts; a test asserts a per-run percentage never renders.
  - _Requirements: R13.3_

- [ ] **4c.3 `coverage liveness --from-run-records`**
  - Fold per-run files into corpus liveness.
  - **Definition of done:** folding the run-record tree reproduces the same table as scoring the
    traces directly, for runs where both exist.
  - _Requirements: R13.5_

- [ ] **4c.4 Run-UI eval panel**
  - Follows `TestResultsPanel` / `GuardrailsPanel` conventions; abstentions visible by default.
  - **Definition of done:** the 2026-09-13 smoke run displays
    `CHK-guardrail-fp-budget: na — no guardrail_check spans` without opening a log.
  - _Requirements: R13.4, R13.7_

## Phase 4d — Feed-forward discipline (R14)

- [ ] **4d.1 CI gate: eval vocabulary must not reach an agent prompt**
  - Scans prompt-construction paths for check ids, FM ids, liveness vocabulary.
  - **Definition of done:** gate fails on a deliberately planted `FM-005` in a prompt template;
    passes on the current tree; product gate results untouched.
  - _Requirements: R14.1, R14.2, R14.3_

- [ ] **4d.2 Assert no eval verdict is written into a lesson**
  - **Definition of done:** a test asserts `memory/lessons.py` records carry no check or FM ids;
    FM-013 remains the lessons detector.
  - _Requirements: R14.7_

- [ ] **4d.3 Corpus coverage as run selection**
  - `never measured` dimension cells readable as a run-selection input.
  - **Definition of done:** selection changes which scenario contracts run; a test asserts the
    emitted contract is byte-identical to the same contract selected any other way.
  - _Requirements: R14.5, R14.6_

- [ ] **4d.4 Record configuration changes as human decisions**
  - A timeout, threshold or retry ceiling changed on eval evidence is recorded with the finding
    that motivated it, and never applied automatically.
  - _Requirements: R14.8_

## Phase 5 — Guardrail and interrupt telemetry — BLOCKED on alignment Phase 1

- [ ] **5.1 `emit_guardrail_decision` in `harness/telemetry.py`**
  - `logs/guardrails.jsonl`; `writer: "harness"`; fields per R5.2 including `scored_text_source`.
  - **Definition of done:** written for pass **and** fail decisions; a read-only logs dir warns
    and the run completes.
  - _Requirements: R5.1, R5.2, R5.3, R5.7_

- [ ] **5.2 Convert `route_after_behavioral` first**
  - `langgraph_guardrail_nodes.py:273` writes through the module; structlog line retained for
    humans, no longer the only record.
  - **Definition of done:** a LangGraph run produces `guardrails.jsonl` rows with
    `scored_text_source: "last_12_ai_messages"`.
  - _Requirements: R5.4_

- [ ] **5.3 Convert remaining guardrail call sites**
  - **Definition of done:** no guardrail decision reaches only structlog; a test asserts every
    guardrail module imports the writer.
  - _Requirements: R5.4_

- [ ] **5.4 `parse_guardrails_jsonl` → `guardrail_check` spans**
  - **Definition of done:** `CHK-guardrail-fp-budget` semantics unchanged; `no_producer` flag
    clears for the LangGraph path.
  - _Requirements: R5.5_

- [ ] **5.5 `emit_interrupt` + `parse_interrupts_jsonl`**
  - LangGraph `interrupt()`, CLI HITL, `hitl_source` transitions → `logs/interrupts.jsonl` →
    `human_interrupt` spans.
  - **Definition of done:** `CHK-interrupt-latency` leaves `unreachable`; R4.6's allow-list entry
    is removed in the same change.
  - _Requirements: R6.1, R6.2, R6.3, R6.5_

- [ ] **5.6 `emit_terminal_state`**
  - Exit condition + whether `finalize()` ran.
  - _Requirements: R6.4_

- [ ] **5.7 Replay the 2026-09-13 smoke brief**
  - **Definition of done:** `CHK-guardrail-fp-budget` returns `fail` with the four retry scores
    (5%, 0%, 9%, 0%) as evidence, and `CHK-interrupt-latency` decides rather than abstaining.
    Until this task passes, no document claims either check caught anything.
  - _Requirements: R5.6, R6.5, R11.6_

## Phase 6 — The six hypothesis failure modes

- [ ] **6.1 `origin: hypothesis` in the taxonomy loader**
  - Plus `hypothesis_evidence`; excluded from active coverage counts and origin shares.
  - **Definition of done:** `taxonomy coverage` reports hypothesis modes in their own row.
  - _Requirements: R9.1, R9.2, R9.3_

- [ ] **6.2 Seed FM-019…FM-024**
  - All `origin: hypothesis`, evidence = the smoke run id + its README. Taxonomy version bumped.
  - **Definition of done:** no FM claims an annotation it does not have.
  - _Requirements: R8.1, R9.2_

- [ ] **6.3 `CHK-run-record-complete` (FM-021)**
  - Start here: it fires on the existing corpus immediately and needs no new telemetry.
  - _Requirements: R8.1, R8.7_

- [ ] **6.4 `CHK-write-path-scope` (FM-022)**
  - Reports nesting depth.
  - _Requirements: R8.4, R8.7_

- [ ] **6.5 `CHK-test-collection-nonempty` (FM-020)**
  - Distinct from FM-006: vacuous, not absent.
  - _Requirements: R8.3, R8.7_

- [ ] **6.6 `CHK-watchdog-enforced` (FM-019)**
  - Conjunction rule: over timeout **and** no `watchdog_expired` terminal state. Needs 5.6.
  - _Requirements: R8.2, R8.7_

- [ ] **6.7 `CHK-no-rewind-after-artifact` (FM-023)**
  - v1 narrow rule only: re-entry triggered by a guardrail error whose phase differs from the
    phase re-entered.
  - **Definition of done:** a legitimate test-failure-driven re-entry fixture returns `pass`; the
    narrow rule is documented in the check docstring with its reason.
  - _Requirements: R8.5, R8.7_

- [ ] **6.8 Retroactive scoring over the existing corpus**
  - **Definition of done:** results recorded with corpus kind and `n`; nothing described as
    observed or prevalent.
  - _Requirements: R8.7, R8.8_

- [ ] **6.9 Promotion path wired, not exercised**
  - `taxonomy propose --from-annotations` surfaces which hypothesis modes unaided annotation
    independently reached. No auto-promotion on a check firing.
  - **Definition of done:** a test asserts a firing check does not promote; promotion requires an
    annotation record with an indexed `trace_id`.
  - _Requirements: R9.4, R9.5, R9.6_

## Phase 7 — Orphan signals

- [ ] **7.1 Re-point `CHK-evaluator-capitulation` at `qa_verdict` spans**
  - Delete the hand-rolled artifact re-parse at `verification.py:242–261`; keep `raw_result` as
    fallback.
  - **Definition of done:** outcomes unchanged on existing fixtures (task 2.5 guard); one JSON
    parser fewer in the check layer.
  - _Requirements: R7.1, R7.2_

- [ ] **7.2 `CHK-subagent-fanout-bounded`**
  - Consumes `subagent_start` / `subagent_stop`; bounds fan-out and catches orphaned subagents.
  - _Requirements: R7.1, R7.4_

- [ ] **7.3 Fold `session_start` into `CHK-run-record-complete`**
  - _Requirements: R7.1, R7.3_

- [ ] **7.4 Delete the `regression_check` parser**
  - **Definition of done:** parser and span type removed; decision and reason recorded in
    `design.md` §4; R4.6's gate would catch a future re-introduction without a consumer.
  - _Requirements: R7.1, R7.3, R7.5_

- [ ] **7.5 Assert zero orphans**
  - **Definition of done:** a test fails when any span type has a parser and no consumer.
  - _Requirements: R7.1_

## Phase 8 — Harness efficiency (spends ≤ $1.00, human-triggered)

- [ ] **8.1 Bare-provider control runner**
  - Same brief, one provider call; wall, tokens, cost recorded as a trace with `arm: "control"`
    reusing `harness-alignment` R1.
  - **Definition of done:** `--dry-run` resolution printed and approved before any call.
  - _Requirements: R10.1, R10.2, R10.5_

- [ ] **8.2 `overhead_ratio` / `cost_ratio` in the report**
  - With `n` and the control trace id; `n=1` renders `ANECDOTE`.
  - **Definition of done:** the 1600 s / 1.528 s observation renders as an anecdote, not a ratio.
  - _Requirements: R10.3, R10.4, R10.7_

- [ ] **8.3 `CHK-overhead-ratio` (FM-024)**
  - Ceiling from the scenario contract, not hardcoded; `not_applicable` with no control.
  - _Requirements: R8.6, R10.6_

- [ ] **8.4 Resolve open decision 9.3**
  - Decide whether overhead reports in Tier A or only in the ladder; record the decision.
  - _Requirements: R10.3_

---

## Minimum defensible slice

**Phase 1, plus tasks 2.1–2.4, plus 6.3.** Liveness measured and published, checks declaring
what they read, and one new check that fires on the corpus that already exists. That converts
"20 checks registered" into a number that means something.

If even that is too long: **tasks 1.3 and 1.4**. Publish the liveness table and correct the
coverage claims it invalidates. No code, and it removes the most misleading sentence the repo
currently ships.
