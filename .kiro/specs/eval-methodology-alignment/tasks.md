# Implementation Plan — Eval Methodology Alignment

**Spec ID:** `eval-methodology-alignment`
**Requirements:** [`requirements.md`](./requirements.md) · **Design:** [`design.md`](./design.md)

9 phases, 47 tasks. Nothing is checked off — this plan has not been executed.

---

## How to execute this plan

- Work **one task at a time, in order**. Do not batch phases.
- Every task lists a **Definition of done**. Do not mark it complete until each bullet is
  literally true.
- Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run mypy evals/`
  before marking any task complete.
- **Do not spend money** outside tasks 2.5 and 7.4, both human-triggered and capped.
- **Phase 4 is human work.** An agent may prepare the sample, run the tool, and process the
  output. It may not annotate, and it may not mark 4.2–4.4 complete. If you are an agent
  reading this: stop at 4.1 and say so.

Cursor prompt shape:

```
Read .kiro/specs/eval-methodology-alignment/requirements.md and design.md for context.
Implement task 1.2 from .kiro/specs/eval-methodology-alignment/tasks.md.
Do not start any other task. Stop when its Definition of done is satisfied and
`uv run ruff check . && uv run mypy src/ evals/ && uv run pytest tests/unit` passes.
```

---

## Phase 0 — Ground truth about the present

- [ ] **0.1 Freeze the current corpus as a baseline artifact**
  - Copy `evals/traces/index.db` and the 50 trace JSONs to
    `evals/baselines/corpus-2026-09-13/` with a `README.md` recording: 50 traces, 0 spans,
    1 backend, 1 scenario, 1 status, 2-second creation span.
  - **Definition of done:** the frozen copy exists; a test asserts it is never written to.
  - _Requirements: R2.5, R15.4_

- [ ] **0.2 Run census script — both trees**
  - `scripts/run_census.py` — counts `workspace/` (empty vs artifacts-only vs logs) **and**
    `output/runs/` (`run.json`, `state.json`, `logs/*.jsonl`, receipts), with backend,
    status and date-span breakdowns. Emits JSON and a markdown table.
  - **Definition of done:** reproduces `workspace/` 440 / 221 empty / 219 artifacts-only /
    0 with logs, and `output/runs/` 211 dated dirs (+18 stray) / 210 run.json / 141 state.json / 60 costs.jsonl
    / 8 receipts, backends langgraph 148 · crewai 1 · claude-agent-sdk 1 · unset 60, span
    2026-07-06 → 2026-09-13.
  - _Requirements: R5.6_

- [ ] **0.3 Record the audit in the journal**
  - `docs/journal/2026-09-13-eval-methodology-audit.md` — what the census found, verbatim
    numbers, the `prompts.py:23` root cause.
  - **Definition of done:** entry follows house conventions; `journey.md` updated.
  - _Requirements: R15.4_

## Phase 1 — Harness-owned telemetry

- [ ] **1.1 `TelemetryWriter`**
  - New `src/ai_team/harness/telemetry.py` per design §2.1, writing under
    `output/runs/<run_id>/logs/` beside `run.json`. All records stamped `writer: "harness"`
    by the module, not by callers.
  - **Definition of done:** unit tests for every record type; `writer` cannot be overridden
    from a call site (test asserts this).
  - _Requirements: R1.1, R1.2, R1.6, R1.7, R2.1_

- [ ] **1.2 Wire it into the `Backend` wrapper**
  - Construct in `run_backend(...)`; hand to the backend as a callback object; close on exit.
  - A backend that ignores the callback still produces `session.json`, one `phase_start`, and
    a terminal `phase_end`.
  - **Definition of done:** a stub backend that calls nothing still yields a trace with
    ≥2 spans and a resolved `scenario_id`.
  - _Requirements: R1.3, R1.7_

- [ ] **1.3 Migrate `context_pressure.py`**
  - Its direct `phases.jsonl` write becomes a `TelemetryWriter.phase_end(...)` call. No second
    writer remains.
  - **Definition of done:** grep for `phases.jsonl` in `src/` returns only `telemetry.py`
    and the trace parsers.
  - _Requirements: R1.3_

- [ ] **1.4 Delete the agent logging instruction**
  - Remove line 23 of `agents/prompts.py`. Do not replace it with a weaker instruction.
  - **Definition of done:** grep for `phases.jsonl` in any prompt template returns nothing;
    a test guards it.
  - _Requirements: R1.5_

- [ ] **1.5 Soft-failure path**
  - `OSError` on write → warning + `degraded: true` in `session.json`; run completes.
  - **Definition of done:** read-only logs dir test passes and the run succeeds.
  - _Requirements: R1.4, R16.3_

- [ ] **1.6 Backend write guard**
  - Test that no module under `src/ai_team/backends/` writes to `logs/`.
  - **Definition of done:** guard fails when a write is reintroduced.
  - _Requirements: R1.3, R16.1_

## Phase 2 — Corpus

- [ ] **2.1 `unindexable` and `partial` states**
  - Add to the trace model and builder per design §4.1; empty workspaces skipped.
  - **Definition of done:** table-driven tests over empty / artifacts-only / logs-only /
    complete workspace shapes.
  - _Requirements: R3.1, R3.3, R5.1_

- [ ] **2.2 Exclude `unindexable` from rates**
  - Numerators, denominators, sampling defaults; `--include-unindexable` for corpus health.
  - **Definition of done:** a corpus of 10 traces, 4 unindexable, reports `n=6` with the
    excluded count shown separately.
  - _Requirements: R3.2, R3.5_

- [ ] **2.3 Idempotent reclassification migration**
  - `index rebuild` reclassifies the existing 50 under the new rules.
  - **Definition of done:** running twice produces identical output; the frozen baseline from
    0.1 is untouched.
  - _Requirements: R3.4_

- [ ] **2.4 Re-index from `output/runs/` — the single highest-value task here**
  - Make `output/runs/` the primary source; join to artifacts via `run.json:workspace_dir`;
    keep `--workspace-root` as a secondary source, no longer the default. Recovery
    extraction per R5.4; record recovered sources per trace.
  - **Definition of done:** `index stats` reports ≥200 traces, ≥3 distinct backends and a
    ≥60-day span, with `backend` and `final_status` taken from run records rather than
    inferred. Costs **$0.00**.
  - _Requirements: R5.1, R5.2, R5.3, R5.4, R5.5_

- [ ] **2.4b Shortfall report before any spend**
  - Print, per R4 floor, what the re-indexed corpus is still short by and which
    backend/scenario cells are empty.
  - **Definition of done:** report runs free and is read before task 2.5 is started; task
    2.5 refuses to start without it.
  - _Requirements: R5.6, R5.8_

- [ ] **2.5 Fill remaining cells — SPENDS ≤ $10.00, human-triggered**
  - Print the R5.3 shortfall report; choose cells; `--dry-run` first; run sequentially.
  - **Definition of done:** every dollar spent is attributable to a named empty cell; the
    resolver refuses above ceiling.
  - _Requirements: R5.3, R5.4_

- [ ] **2.6 `CorpusProfile` and the `NON-REPRESENTATIVE` stamp**
  - Per design §4.2; rendered by the renderer, never by prose.
  - **Definition of done:** the stamp appears on every report and sample manifest derived from
    a sub-floor corpus and names the specific floors.
  - _Requirements: R4.1, R4.2, R4.3, R4.4, R4.5, R4.6_

## Phase 3 — FM-018 and provenance

- [ ] **3.1 Add FM-018 to the taxonomy**
  - `self_reported_telemetry`, layer `harness`, detection `check`, origin `open_coding`
    pending evidence — stamp `hypothesis` until Phase 5 confirms it.
  - **Definition of done:** `taxonomy coverage` includes it; `taxonomy_version` → `1.3.0`.
  - _Requirements: R2.2_

- [ ] **3.2 `CHK-telemetry-provenance`**
  - `pass` / `fail` / `na` semantics per design §3.1, including `na` on no records.
  - **Definition of done:** three fixtures committed; Tier A cost unchanged at $0.00.
  - _Requirements: R2.3, R2.4, R2.6, R16.4_

- [ ] **3.3 Score the frozen baseline**
  - Run the check over `evals/baselines/corpus-2026-09-13/`; record the result.
  - **Definition of done:** result recorded as a baseline, explicitly not a regression.
  - _Requirements: R2.5_

- [ ] **3.4 `origin` and `status` fields on every FM**
  - Schema + loader + migration stamping FM-001…FM-013 `essay`, FM-014…FM-017 `reference`.
  - **Definition of done:** no entry is `open_coding` without `evidence_annotations`; loader
    rejects one that is.
  - _Requirements: R9.1, R9.2, R9.3_

- [ ] **3.5 Report origin share**
  - `taxonomy coverage` and `SuiteReport` show counts and share by origin.
  - **Definition of done:** today's output reads 13 essay / 4 reference / 1 hypothesis /
    **0 open_coding**.
  - _Requirements: R9.4_

## Phase 4 — Error analysis (HUMAN — not delegable)

- [ ] **4.1 Prepare the sample** *(agent may do this)*
  - `sample --strategy stratified -n 100 --seed 1` over the post-Phase-2 corpus; print the
    imbalance report and the corpus stamp.
  - **Definition of done:** manifest written; imbalances named; stamp shown.
  - _Requirements: R4.3, R8.2_

- [ ] **4.2 Annotate 30 traces unaided** *(human only)*
  - No clustering, no proposals, no model output of any kind. Records carry `unaided: true`.
  - **Definition of done:** ≥30 records with `unaided: true` in `evals/annotations/`.
  - _Requirements: R7.1, R7.2, R7.6_

- [ ] **4.3 Continue to saturation** *(human only)*
  - Stop at 20 consecutive traces with no new tag, or at 100. Record which.
  - **Definition of done:** terminating condition recorded in the session manifest.
  - _Requirements: R7.5_

- [ ] **4.4 Axial coding** *(human decides; tooling clusters)*
  - `taxonomy propose --from-annotations`; accept / merge / reject by hand into 5–8 categories.
  - **Definition of done:** categories are specific enough for a second reader; none was
    written by the clusterer directly into `failure_modes.yaml`.
  - _Requirements: R8.3, R8.4_

- [ ] **4.5 Frequency table**
  - Counts, percentages, Wilson 95% CIs, stamped with `sample_id`, `n`, corpus profile.
  - **Definition of done:** table renders; no figure appears without its stamp.
  - _Requirements: R8.1, R8.2, R15.1_

## Phase 5 — Taxonomy re-derivation

- [ ] **5.1 Classify every existing FM against the annotations**
  - `confirmed` / `unobserved` / `refined`, with evidence for each confirmation.
  - **Definition of done:** all 18 classified; promotions carry annotation ids.
  - _Requirements: R10.1, R9.5_

- [ ] **5.2 Mark unobserved modes**
  - `status: unobserved` with the sample they were not observed in. Nothing deleted.
  - **Definition of done:** unobserved modes excluded from active coverage counts and still
    present in the file.
  - _Requirements: R10.2_

- [ ] **5.3 Add newly observed modes**
  - New FMs with `origin: open_coding` and evidence; no id reuse.
  - **Definition of done:** loader accepts; `taxonomy_version` → `2.0.0`; old traces still
    readable.
  - _Requirements: R10.3, R10.4_

## Phase 6 — Annotation ergonomics

- [ ] **6.1 Resolve open decision 2 (TUI vs local web)**
  - Write the decision and its rationale into design §11 before building.
  - **Definition of done:** decision recorded with the trade-off stated.
  - _Requirements: R13.5_

- [ ] **6.2 Single-keystroke navigation and tagging**
  - No `$EDITOR` round-trip on the common path.
  - **Definition of done:** annotating a trace with one tag takes one keystroke plus the tag.
  - _Requirements: R13.1_

- [ ] **6.3 Progress, elapsed time, distinct-tag counter**
  - The saturation curve is visible while annotating.
  - **Definition of done:** `k of n`, elapsed, and distinct-tag count update per trace.
  - _Requirements: R13.2, R7.5_

- [ ] **6.4 Filter, order, resume**
  - By backend, scenario, status, duration; interrupted sessions resume from the manifest.
  - **Definition of done:** a killed session resumes at the next unannotated trace.
  - _Requirements: R13.3_

- [ ] **6.5 Domain-shaped trace rendering**
  - Phase timeline, first divergence, generated file list, test output — not raw JSON.
  - **Definition of done:** a reviewer unfamiliar with the trace schema can read a card.
  - _Requirements: R13.4_

- [ ] **6.6 Re-assert the no-model-output constraint**
  - Extend the `annotate.py` docstring to cover every new surface added in 6.2–6.5.
  - **Definition of done:** no code path in the annotation UI can display model output.
  - _Requirements: R7.3, R13.6_

## Phase 7 — Judges

- [ ] **7.1 Judge eligibility gate**
  - An FM may be `detection: judge` only under R11.1; `judge_rationale` required.
  - **Definition of done:** loader rejects a judge-detection FM that fails eligibility.
  - _Requirements: R11.1, R11.2_

- [ ] **7.2 `manual` as a first-class detection value**
  - Reported as `manual`, not as a coverage gap.
  - **Definition of done:** coverage output distinguishes `check` / `judge` / `manual`.
  - _Requirements: R11.3_

- [ ] **7.3 Retire or re-scope the FM-001 judge prompt**
  - FM-001 is `detection: check`; its judge prompt gates nothing.
  - **Definition of done:** the prompt is removed or bound to an eligible FM; the stale
    `n: 0` alignment report is removed with it.
  - _Requirements: R11.4_

- [ ] **7.4 Align and validate — SPENDS ≤ $5.00, human-triggered**
  - Only for FMs with ≥100 labels. Binary verdicts, exclusion rules, labeled examples on both
    sides. Align on dev, validate once per `prompt_hash` on test.
  - **Definition of done:** TPR, TNR, κ and n reported; accuracy never reported alone.
  - _Requirements: R12.1, R12.2, R12.3, R12.4, R12.5, R12.6_

- [ ] **7.5 Refusal coverage**
  - 100% branch coverage on the three refusals in design §6.2.
  - **Definition of done:** coverage report confirms; no refusal has an override flag.
  - _Requirements: R16.2_

## Phase 8 — Cadence and claims

- [ ] **8.1 Staleness reporting**
  - `index stats` reports days since the last annotation and traces added since.
  - **Definition of done:** reported, never gated.
  - _Requirements: R14.3, R14.4_

- [ ] **8.2 Review triggers**
  - Document the 2–4 week cycle, the weekly 10–20 outlier review, and the event triggers
    (model change, new backend, component toggle).
  - **Definition of done:** written into `docs/EVAL_METHODOLOGY.md`.
  - _Requirements: R14.1, R14.2_

- [ ] **8.3 Corpus-kind rendering**
  - Every rate renders `FIXTURE-ONLY` / `CORPUS` / `LIVE`.
  - **Definition of done:** a Tier A fixture run cannot render a rate without
    `FIXTURE-ONLY`.
  - _Requirements: R15.1, R15.2_

- [ ] **8.4 Demote generic metrics**
  - `metrics.py` scorecard output labeled as a sampling signal, not a quality claim.
  - **Definition of done:** no generic metric appears as a headline figure.
  - _Requirements: R15.3_

- [ ] **8.5 Dated corpus-state table + CI staleness warning**
  - `docs/EVAL_METHODOLOGY.md` carries a table matching `index stats`; CI warns past 30 days.
  - **Definition of done:** table matches current output; warning fires on a stale table.
  - _Requirements: R15.4_

- [ ] **8.6 Fix the broken gate-status link**
  - Create `docs/campaign/EVAL_GATE_STATUS.md` or remove both references to it.
  - **Definition of done:** no dangling link remains in `docs/`.
  - _Requirements: R15.6_

- [ ] **8.7 Claim audit of external artifacts**
  - Every post, showcase page, and deck derived from this work states corpus kind and `n`.
  - **Definition of done:** an artifact reporting a rate without `n` is treated as a defect
    and corrected.
  - _Requirements: R15.5_

---

## Minimum defensible slice

**Phases 1, 2, 4.** Harness-owned telemetry, a corpus that clears its floors, and 100 traces
open-coded by a human.

If that is too long: **Phase 1 plus task 4.2.** Instrument the runs, annotate thirty of them
yourself. Thirty traces read by hand will change what you build next more than the remaining
eight phases combined.
