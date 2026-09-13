# Requirements — Eval Methodology Alignment

**Spec ID:** `eval-methodology-alignment`
**Status:** Draft for implementation
**Owner:** Rick Zakharov
**Target repo:** `ai-team` (extends `src/ai_team/harness/`, `evals/trace/`, `evals/annotate.py`)
**Created:** 2026-09-13
**Depends on:** [`../eval-harness/`](../eval-harness/) — Trace boundary (R1), sampling (R2),
annotation (R3), taxonomy (R5), golden sets and alignment (R8), tiers and budget (R11),
provenance (R14). [`../harness-alignment/`](../harness-alignment/) — arms (R1), FM-014…FM-017.
Neither is restated.

---

## Introduction

This repo has built the error-analysis loop twice over and never run it once.

`evals/` contains a trace store, five sampling strategies, an open-coding TUI that
deliberately refuses to show model suggestions, an axial-coding clusterer, a golden-label
store with deterministic dev/test splits, judge alignment with bootstrap CIs, Cohen's κ,
prevalence bias correction, a verdict cache, a budget ledger, and a gate. `docs/EVAL_METHODOLOGY.md`
cites Husain and Shankar by name and states the loop correctly. The machinery is real.

The inputs are not.

| Stage | Implemented | Has ever run on real data |
| --- | --- | --- |
| Trace capture | yes | **no** — 50 traces, 0 spans |
| Sampling | yes | once; asked for 100, got 50, all one stratum |
| Open coding | yes | **no** — `evals/annotations/` is empty |
| Axial coding | yes | **no** — nothing to cluster |
| Taxonomy | 17 FMs | derived from an essay, not from traces |
| Golden labels | yes | **no** — 0 labels |
| Judge alignment | yes | `n: 0`, `eligible_to_gate: false` |
| Tier A gate | yes | scores 94 synthetic fixtures |

The cause is upstream of all of it, and it is two things.

**The corpus is built from the wrong tree.** `trace backfill` defaults to
`--workspace-root ./workspace`, which holds what the *agents* wrote: 440 directories, 221
empty, 219 containing generated `src/` and `tests/` and no telemetry. What the *harness*
wrote went to `./output/runs/` — **211 dated run directories** (plus 18 stray entries: eight GUID dirs and loose `h1`–`h4`, `p`, `ws`, `artifacts/`, `logs/`, `reports/`, `state.json` — the same run-id litter the July journal recorded), of which **210** carry a
`run.json` (backend, `workspace_dir`, `completed_at`, `final_status`), **141** a
`state.json` (actual cost, total tokens), **60** a `logs/costs.jsonl`, and **8** a signed
receipt. Backends recorded there: `langgraph` 148, `crewai` 1, `claude-agent-sdk` 1, unset
60, across **2026-07-06 → 2026-09-13 — a 69-day span.** The corpus indexed as one backend
over 1.97 seconds could have been three backends over 69 days, for $0.00, on day one.

**Phase telemetry is requested from the model rather than written by the harness.**
`phases.jsonl` yields the phase and retry spans every trajectory check reasons over. Its
only code writer is `src/ai_team/harness/context_pressure.py` (added 2026-09-12, one
`phase_end` row); otherwise it is asked for at `prompts.py:23`: *"Write phase transition
entries to workspace/logs/phases.jsonl."* **Zero such files exist under `workspace/` or
`output/runs/`.** `audit.jsonl` and `costs.jsonl`, by contrast, have real code writers
(`tools/bus.py`, `core/results/writer.py`, `claude_agent_sdk_backend/costs.py`). Phase
telemetry is the single signal left to a prompt, and it is the one the checks need most.

So the harness is not measuring `ai-team`. It is measuring its own fixtures, honestly
labelled as such in `evals/golden/README.md` and `docs/EVAL_METHODOLOGY.md`, and the
honesty has been doing the work that data should be doing.

### What this spec adds

| Area | Gap today | Requirement |
| --- | --- | --- |
| Corpus source | backfill reads `workspace/`; 210 run records sit unread in `output/runs/` | R5 |
| Telemetry ownership | phase records asked for in a prompt; 0 `phases.jsonl` anywhere | R1, R2 |
| Backfill honesty | empty trace recorded as `failed` | R3 |
| Corpus diversity | 50 traces, 1 backend, 1 scenario, 1 status, 2-second span | R4, R5 |
| Scenario variation | one contract shape; no dimension sampling | R6 |
| Error analysis | never performed | R7, R8 |
| Taxonomy provenance | no FM records where it came from | R9, R10 |
| Judge scope | 1 prompt, 17 FMs, 0 labels | R11, R12 |
| Annotation ergonomics | `$EDITOR` round-trip per trace | R13 |
| Review cadence | none | R14 |
| Claim discipline | fixture pass rate reads like a system pass rate | R15 |
| Test hygiene | — | R16 |

---

## R1 — Harness-owned phase telemetry

**User story.** As the owner of the eval harness, I want run telemetry written by harness
code on the execution path, so that a measurement does not depend on an agent choosing to
report itself.

### Acceptance criteria

1. WHEN any backend begins a phase, the harness SHALL append a `phase_start` record to
   `<workspace>/logs/phases.jsonl` containing `phase`, `timestamp`, `run_id`, `backend`, and
   `writer: "harness"`.
2. WHEN any backend completes or aborts a phase, the harness SHALL append a `phase_end`
   record carrying `end_status`, `duration_s`, and `context_pressure` where a token count is
   available, and `context_pressure: null` where it is not.
3. The harness SHALL write these records from a single module
   (`src/ai_team/harness/telemetry.py`) invoked by the `Backend` protocol wrapper, so that a
   new backend inherits telemetry without implementing it.
4. IF a telemetry write fails, THEN the harness SHALL record a warning on the run and
   continue; telemetry failure SHALL NOT fail a run.
5. The instruction *"Write phase transition entries to workspace/logs/phases.jsonl"* SHALL be
   **removed** from `agents/prompts.py`, not supplemented. Agent-written telemetry is the
   defect, and leaving the instruction in place makes provenance unresolvable.
6. WHERE a backend can report per-call token and dollar usage, the harness SHALL append it to
   `<workspace>/logs/costs.jsonl` with `writer: "harness"` and a `source` field distinguishing
   `provider_response` from `estimated`.
7. Harness-written telemetry SHALL be co-located with the run record under
   `output/runs/<run_id>/logs/`, which is the tree the corpus reads (R5.1). Writing run
   telemetry only into `workspace/<run_id>/logs/` is the defect this requirement removes.
8. The harness SHALL write `<run_record>/logs/session.json` at run start with `run_id`,
   `scenario_id`, `backend`, `arm`, `model_ids`, `git_sha`, and `started_at`, so that a trace
   built later never has to infer `scenario_id` from a directory name.

## R2 — Telemetry provenance is checkable (FM-018)

**User story.** As a reviewer, I want to see at a glance whether a trace's telemetry was
written by the harness or by the model, so that I know what a number is worth.

### Acceptance criteria

1. Every telemetry record SHALL carry a `writer` field with value `harness` or `agent`.
2. The taxonomy SHALL gain **FM-018 `self_reported_telemetry`**, layer `harness`, detection
   `check`, bound to `CHK-telemetry-provenance`.
3. `CHK-telemetry-provenance` SHALL fail a trace WHEN any span derives from a record whose
   `writer` is `agent` or absent, and SHALL pass WHEN every record is `writer: harness`.
4. The check SHALL run in Tier A at $0.00 and SHALL be scoreable retroactively over the
   existing corpus.
5. WHEN the check is run over the corpus as it stands on 2026-09-13, the report SHALL show
   FM-018 present in all 50 traces. That result is the baseline, not a regression.
6. `CHK-telemetry-provenance` SHALL return `na` — not `pass` — for a trace with no telemetry
   records at all, so that an empty run is never counted as clean.

## R3 — Honest backfill states

**User story.** As an analyst, I want an unreadable run to be distinguishable from a failed
run, so that corpus statistics are not poisoned by absence.

### Acceptance criteria

1. WHEN the trace builder finds no log files and no spans for a workspace, it SHALL record
   `status: "unindexable"` with `unindexable_reason`, and SHALL NOT record `status: "failed"`.
2. `unindexable` traces SHALL be excluded from every pass-rate numerator and denominator, and
   SHALL be counted and displayed separately in `index stats` and in `SuiteReport`.
3. WHEN a workspace directory is empty, the builder SHALL skip it and SHALL NOT create a trace.
4. `evals/cli.py index rebuild` SHALL reclassify the 50 existing traces under these rules in
   a single migration, and the migration SHALL be idempotent.
5. Sampling strategies SHALL exclude `unindexable` traces by default, with `--include-unindexable`
   available for corpus-health work.

## R4 — Corpus diversity floor

**User story.** As an analyst, I want the harness to refuse to call a monoculture a corpus,
so that I do not draw conclusions from 50 copies of one run.

### Acceptance criteria

1. The harness SHALL compute a `CorpusProfile` over the indexed corpus with counts by
   `backend`, `scenario_id`, `status`, `arm`, and calendar day.
2. The corpus SHALL be considered **representative** only WHERE all of: `n_indexable ≥ 100`,
   distinct backends ≥ 3, distinct `scenario_id` ≥ 4, distinct statuses ≥ 2, and span of
   `started_at` ≥ 14 days.
3. IF any floor is unmet, THEN every report and sample manifest derived from that corpus
   SHALL carry a `NON-REPRESENTATIVE` stamp naming the specific unmet floors.
4. The stamp SHALL be rendered by the report renderer, never asserted in prose. A document
   that states a corpus rate without the stamp is a defect.
5. `scenario_id: "unknown"` SHALL count as zero distinct scenarios, not one.
6. Corpus floors SHALL NOT gate CI. An undersized corpus is a state to display, not a build
   to break.

## R5 — Corpus construction from the run-record tree

**User story.** As the owner, I want the corpus built from where the harness actually
writes, so that new spend is only used for what is genuinely not on disk.

### Acceptance criteria

1. The trace builder SHALL take **`./output/runs/`** as its primary source, reading
   `run.json`, `state.json`, `logs/*.jsonl` and `receipt.json` where present, and SHALL join
   each run to its artifacts via the `workspace_dir` field that `run.json` already carries.
2. `--workspace-root` SHALL be retained as a secondary source for runs with no record in
   `output/runs/`, and SHALL no longer be the default.
3. WHEN a run record supplies `backend`, `completed_at`, or `final_status`, the builder
   SHALL use it rather than inferring from a directory name, and `scenario_id` SHALL fall
   back to `unknown` only when no record supplies it.
4. The builder SHALL extract, from a run with records but no phase telemetry, whatever is
   recoverable — backend, status, cost, tokens, duration, generated file inventory, test
   results — and SHALL mark the resulting trace `partial: true` with a list of recovered
   sources.
5. `partial` traces SHALL be eligible for open coding but SHALL NOT be eligible for judge
   golden labels, since their evidence is incomplete.
6. The harness SHALL report, before any re-run spend is approved, how many traces each floor
   in R4 is short by **after** the re-index, and which scenario/backend cells remain empty.
7. WHERE re-runs are still required to clear a floor, they SHALL be executed under an
   explicit ceiling of **$10.00**, sequentially, with `--dry-run` resolution printed and
   approved first.
8. The re-index SHALL be free. No requirement in this spec authorizes spend before R5.6 has
   been run and read.

## R6 — Scenario dimension sampling

**User story.** As an analyst, I want the corpus to vary along dimensions I chose
deliberately, so that diversity is designed rather than hoped for.

### Acceptance criteria

1. The repo SHALL define `evals/scenarios/dimensions.yaml` enumerating the axes along which a
   scenario can vary — at minimum: task size, stack familiarity, specification completeness
   (including the `thin` brief left open by `harness-alignment` §9.4), presence of an existing
   codebase, and expected failure surface.
2. Scenario generation SHALL proceed in two steps: emit structured dimension tuples, then
   render each tuple to a scenario contract — never generate prose contracts directly.
3. Each generated scenario SHALL record its dimension tuple in its contract, so that corpus
   coverage can be reported per dimension rather than only per `scenario_id`.
4. Generated scenarios SHALL be marked `synthetic: true` and SHALL be reported separately from
   scenarios drawn from real use.
5. WHERE a dimension cell is unrepresented in the corpus, the coverage report SHALL name it as
   `never measured`, distinct from a cell with a zero pass rate.

## R7 — Error analysis is human and unaided

**User story.** As the single annotator, I want the first pass of open coding to be mine
alone, so that the taxonomy reflects what the system does rather than what a model guessed.

### Acceptance criteria

1. Open coding SHALL be performed by one named human annotator — the benevolent dictator —
   recorded in every `AnnotationRecord`.
2. The annotator SHALL complete **≥30 traces with no model assistance of any kind** before any
   clustering, proposal, or suggestion tooling is run over the annotations.
3. `evals/annotate.py` SHALL continue to display no model output of any kind (R3.7 of
   `eval-harness`), and this spec SHALL NOT relax that constraint under any justification.
4. An annotation session SHALL record `unaided: true|false` per record, and
   `taxonomy propose` SHALL refuse to run WHEN fewer than 30 `unaided: true` records exist.
5. The session SHALL continue until **theoretical saturation** — defined operationally as 20
   consecutive traces producing no new open-coding tag — or until 100 traces are annotated,
   whichever comes first, and the terminating condition SHALL be recorded.
6. Annotation SHALL NOT be delegated to a subagent, contractor, or model. A model-labeled
   golden set makes every downstream number meaningless and the harness SHALL provide no
   affordance for producing one.

## R8 — Open codes are counted before they are acted on

**User story.** As the owner, I want failure categories ranked by frequency, so that I fix
what is common rather than what is memorable.

### Acceptance criteria

1. After open coding, the harness SHALL produce a frequency table of axial categories with
   counts, percentages, and Wilson 95% intervals over the annotated sample.
2. The table SHALL name the sample it was computed over (`sample_id`, `n`, corpus profile
   stamp) and SHALL NOT be extrapolated to the corpus without that context.
3. `taxonomy propose` SHALL cluster open-coding tags into candidate categories and SHALL
   present them for human accept/merge/reject — it SHALL NOT write to
   `failure_modes.yaml` directly.
4. Axial categories SHALL be specific enough that a second reader can apply them; the spec's
   working target is 5–8 categories over the first pass.

## R9 — Taxonomy provenance

**User story.** As a reader of the taxonomy, I want to know which failure modes were observed
and which were imagined, so that I can weight them accordingly.

### Acceptance criteria

1. Every entry in `failure_modes.yaml` SHALL carry `origin` with one of: `essay` (derived from
   `docs/posts/failure-taxonomy.md`), `open_coding` (derived from annotations), `reference`
   (derived from an external source, as FM-014…FM-017 are), or `hypothesis`.
2. Every `origin: open_coding` entry SHALL carry `evidence_annotations`: the annotation record
   ids it was derived from, minimum 1.
3. All 17 existing entries SHALL be stamped at their true origin in a single migration —
   FM-001…FM-013 as `essay`, FM-014…FM-017 as `reference` — with no re-labelling of essay
   modes as observed.
4. `taxonomy coverage` SHALL report the count and share of active FMs by origin, and this
   share SHALL appear in `SuiteReport`.
5. WHERE an `origin: essay` mode is later confirmed by open coding, its origin SHALL be
   promoted to `open_coding` and its evidence recorded — promotion requires evidence, never
   argument.

## R10 — Taxonomy re-derivation and retirement

**User story.** As the owner, I want the taxonomy to be answerable to the data, so that it
shrinks when the data does not support it.

### Acceptance criteria

1. After the first open-coding pass, each existing FM SHALL be classified as `confirmed`,
   `unobserved`, or `refined` against the annotations.
2. An `unobserved` mode SHALL NOT be deleted. It SHALL be marked `status: unobserved` with the
   sample it was not observed in, and excluded from active coverage counts.
3. Candidate categories from open coding with no existing FM SHALL be added as new FMs with
   `origin: open_coding`, and SHALL NOT reuse a retired id.
4. `taxonomy_version` SHALL be bumped to `2.0.0` on first re-derivation, and every trace scored
   under a prior version SHALL remain readable.

## R11 — Judges are earned, not assumed

**User story.** As the owner, I want a judge to exist only where a cheap check cannot do the
job and the failure has survived a prompt fix, so that I am not maintaining evaluators for
problems I already solved.

### Acceptance criteria

1. An FM SHALL be eligible for `detection: judge` only WHEN all of: it is `origin: open_coding`
   or `confirmed`; it cannot be decided deterministically from a Trace; and it persisted across
   at least one recorded prompt or harness fix.
2. The FM's `judge_rationale` field SHALL state why a deterministic check cannot decide it.
3. WHERE an FM is not judge-eligible, it SHALL remain `detection: check` or `detection: manual`.
   `manual` SHALL be a first-class detection value reported as such, not a gap.
4. The existing `fm-001-tool-call-omission.v1.md` judge prompt SHALL be retired or re-scoped,
   since FM-001 is `detection: check` and the prompt therefore evaluates nothing that gates.

## R12 — Judge validation discipline

**User story.** As a reviewer, I want every judge's true-positive and true-negative rates on a
held-out split, so that a judge that always says "pass" cannot look good.

### Acceptance criteria

1. A judge SHALL emit a **binary** verdict from a versioned prompt file. Continuous scores
   SHALL NOT gate.
2. Each judge prompt SHALL contain explicit **exclusion rules** — named conditions that are
   *not* the failure — and at least one labeled example of each side.
3. A judge SHALL require **≥100 human labels** for its failure mode before `judge validate`
   may be run, with 100–200 as the working target.
4. Gating eligibility SHALL require TPR ≥ 0.90, TNR ≥ 0.90, κ ≥ 0.70, n ≥ 100 on the test split
   (unchanged from `eval-harness` R8).
5. Overall accuracy SHALL NOT appear as a headline figure anywhere a judge is reported. WHERE
   accuracy is shown, TPR and TNR SHALL be shown beside it.
6. Judge align and validate spend SHALL be capped at **$5.00** for this spec and SHALL be
   human-triggered.

## R13 — Annotation ergonomics

**User story.** As the annotator, I want to move through 100 traces without friction, because
the cost of the loop is the reason it does not happen.

### Acceptance criteria

1. The annotation interface SHALL support single-keystroke advance, back, tag, and flag without
   an `$EDITOR` round-trip for the common path.
2. It SHALL display session progress (`k of n`), elapsed time, and running distinct-tag count so
   the annotator can see saturation approaching.
3. It SHALL support filtering and ordering the sample by backend, scenario, status, and
   duration, and SHALL support resuming an interrupted session.
4. It SHALL render a trace in a form suited to this domain — phase timeline, first divergence,
   generated file list, test output — not a raw JSON dump.
5. It SHALL remain local, dependency-light, and in-repo. No annotation vendor SHALL enter the
   critical path.
6. Every ergonomic addition SHALL be evaluated against R7.3: if it would surface a model's
   opinion, it SHALL NOT be built.

## R14 — Review cadence

**User story.** As the owner, I want error analysis to recur, so that the taxonomy tracks the
system rather than a moment in its history.

### Acceptance criteria

1. The repo SHALL define a recurring review: ≥100 fresh traces open-coded every 2–4 weeks, and
   10–20 outlier traces reviewed weekly between passes.
2. A review SHALL be triggered, regardless of calendar, WHEN the default model changes, a
   backend is added, or a harness component is enabled or disabled.
3. `evals/cli.py index stats` SHALL report days since the last annotation record and the count
   of traces created since, so staleness is visible without ceremony.
4. Staleness SHALL be reported, never gated.

## R15 — Claim discipline

**User story.** As a reader of this repo's public claims, I want to know what corpus a number
came from, so that a fixture pass rate cannot be mistaken for a quality measurement.

### Acceptance criteria

1. Every pass rate SHALL be rendered with its corpus kind: `FIXTURE-ONLY`, `CORPUS`, or `LIVE`.
2. A Tier A result over `evals/fixtures/traces/` SHALL render as `FIXTURE-ONLY` and SHALL NOT be
   described as a measurement of `ai-team` in any document, README badge, or post.
3. Generic or off-the-shelf metrics SHALL be used only as a signal for selecting traces to
   inspect, and SHALL NOT be reported as a quality claim.
4. `docs/EVAL_METHODOLOGY.md` SHALL carry a dated corpus-state table matching the current
   `index stats` output, and CI SHALL warn WHEN the table is more than 30 days older than the
   newest trace.
5. Every external-facing artifact derived from this work — posts, showcase pages, decks — SHALL
   state the corpus kind and `n` for any rate it reports. A claim without `n` is a defect in the
   claim, not a rounding of it.
6. The broken link `docs/campaign/EVAL_GATE_STATUS.md`, referenced from
   `docs/EVAL_METHODOLOGY.md` and `docs/posts/harness-map.md`, SHALL be created or the
   references removed. A gate-status claim pointing at a missing file is the failure mode this
   requirement exists to prevent.

## R16 — Test hygiene

**User story.** As a maintainer, I want this spec's additions to be tested to the same standard
as the harness they instrument.

### Acceptance criteria

1. No test SHALL write to `evals/annotations/`, `evals/golden/`, or `evals/traces/`. Tests
   SHALL use `tmp_path` roots.
2. Every refusal path added by this spec — `taxonomy propose` under 30 unaided records, judge
   validate under 100 labels, re-run above ceiling, `unindexable` exclusion — SHALL reach 100%
   branch coverage.
3. Telemetry writing SHALL be tested for the failure case: a read-only logs directory SHALL
   produce a warning and a completed run.
4. The FM-018 check SHALL have `pass`, `fail`, and `na` fixtures like every other check.

---

## Constraints

| | |
| --- | --- |
| No new package | extends `src/ai_team/harness/`, `evals/trace/`, `evals/taxonomy/`, `evals/annotate.py` |
| No vendor in the critical path | no Braintrust / LangSmith / Arize / DeepEval; consistent with `eval-harness` |
| Budget | ≤ $10 corpus re-runs + ≤ $5 judge work = **≤ $15.00**, additive to the $5 suite and $25 ladder |
| Tier A stays $0.00 | FM-018 and every check added here is deterministic |
| Backwards compatible | traces scored under `taxonomy_version` 1.x remain readable |
| Human step is human | R7 is not delegable, and no task in `tasks.md` may be marked complete by an agent that performed it |

## Non-goals

- Multi-annotator agreement (κ between humans). Single benevolent dictator is the design.
- Online/production monitoring of a deployed system. This is a development-time loop.
- RAG or retrieval evaluation.
- Replacing any existing check's semantics, or re-opening the arm/ladder design.
- Proving a framework ranking. That remains out of reach and `harness-alignment` says why.
