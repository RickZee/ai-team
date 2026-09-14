# Requirements — Eval Claim Surfaces

**Spec ID:** `eval-claim-surfaces`
**Status:** Draft for implementation
**Owner:** Rick Zakharov
**Target repo:** `ai-team` (extends `evals/aggregate.py`, `evals/report.py`, `evals/coverage.py`,
`evals/cli.py`, `evals/store.py`, `docs/`)
**Created:** 2026-09-14
**Cost:** $0.00 — every requirement is satisfied offline against files already on disk.

**Depends on:** [`../eval-harness/`](../eval-harness/) — Trace boundary (R1), check registry
(R5), `SuiteReport` (R13), tiers (R11). [`../eval-methodology-alignment/`](../eval-methodology-alignment/)
— corpus source (R5), review cadence (R14), claim discipline (R15).
[`../eval-coverage/`](../eval-coverage/) — evidence declarations (R1), liveness (R2),
`not_applicable` as first-class (R3), coverage claim discipline (R11).
**None of those are restated here.** Where a criterion below implements one of them it cites
it and adds only what the citation does not already fix.

---

## Introduction

Three specs already describe a correct eval system. This one is about the three places a
human touches it and learns something false.

`eval-methodology-alignment` fixes the **inputs** — the corpus is built from the wrong tree
and phase telemetry is asked of the model. `eval-coverage` fixes the **instruments** — checks
read spans no code writes, and 76.3% of results abstain unreported. Both are correct and
neither covers the following:

1. **`README.md:337` and `evals/README.md:12` tell a new reader to run the audited defect.**
   `uv run python -m evals.cli trace backfill --workspace-root ./workspace` is, verbatim, the
   invocation that produced 50 traces with 0 spans. It is still the documented quickstart. The
   audit is written up in three places; the command a reader actually copies is unchanged.

2. **The report renders fixture arithmetic in the visual grammar of a measurement.**
   `evals/results/tierA_4671d49ae035_eb36475d7c/report.md` §4 publishes
   `FM-006 | harness | 0.976 (n=84, 95% CI [0.917, 0.993]) | — | 82`. Every figure is
   arithmetically correct. There is no corpus stamp, no abstention count, and the `n=84` counts
   files rather than distinct `trace_id`s. Seven of seventeen active failure modes are absent
   from the table with no indication whether they did not occur or could not be seen.

3. **There is no clock.** `index stats` prints four columns of counts. Nothing reports days
   since the last annotation, traces added since, or which R4 diversity floor is unmet.
   `EVAL_METHODOLOGY.md` describes the loop and never says how often it turns. The
   methodology's continuous half exists only as unimplemented spec text — alignment Phase 8,
   0 of 47 tasks done.

### The composition problem

No single number in the current report is wrong. The report as a whole asserts something
nobody decided to assert, because the renderer has no vocabulary for the three facts that
would qualify it:

```
  what the reader sees                 what is true
  ────────────────────────────────────────────────────────────────────────────
  17 FM rates with Wilson CIs          20 checks behaved as written
  n=84                                 72 distinct traces in 94 files
  0.976                                1435 of 1880 results abstained
  FAIL — 182 failed checks             65 of the 182 are one check out of scope
```

This spec's entire content is: make the renderer able to say the right-hand column, make the
quickstart stop teaching the defect, and start a clock. Nothing here improves the eval
system's accuracy. It makes the system's own output legible, which is the precondition for
anyone — including its author — noticing the next defect faster than two months.

---

## R1 — No tracked document presents a command the repo knows to be wrong

**User story.** As a new reader, I want the quickstart to work, because the first command I run
is the one that shapes what I believe the system does.

### Acceptance criteria

1. `README.md` and `evals/README.md` SHALL NOT present `trace backfill --workspace-root
   ./workspace` as the corpus-building path.
2. WHEN `eval-methodology-alignment` task 2.4 has landed, every runnable corpus-building
   snippet in a tracked document SHALL invoke the run-record tree as its primary source.
3. UNTIL task 2.4 lands, each such snippet SHALL carry a one-line caveat naming the defect and
   linking the owning task, so that a reader who runs it knows what they will get. A correct
   caveat satisfies this requirement; a silent wrong command does not.
4. Historical documents SHALL be exempt by path: `docs/journal/`, `docs/eval-runs/`,
   `docs/posts/`, `docs/showcase/`, `docs/campaign/` and `.archive/` record what was run at
   the time and SHALL NOT be rewritten. A defect narrative quoting the wrong command is
   evidence, not an error.
5. CI SHALL fail WHEN a tracked document outside those paths contains a corpus-building
   command whose source argument resolves to `./workspace`. This is the one gate this spec
   adds: it fires on a known-wrong command, never on a data state.
6. `docs/GETTING_STARTED.md` SHALL link the eval entry point at the same prominence as the
   harness and guardrail docs, and that link SHALL reach a page whose first runnable command
   satisfies R1.2 or R1.3.

## R2 — Corpus kind and evidence stamps have exactly one implementation

**User story.** As a maintainer, I want one definition of `FIXTURE-ONLY` in the codebase,
because two renderers that disagree about what corpus they read is a worse defect than neither
of them saying.

### Acceptance criteria

1. `CorpusKind` and the `EVIDENCE-STARVED` threshold SHALL remain defined in
   `evals/coverage.py` — where they already exist as of `f883d75` — and SHALL be imported by
   every other consumer.
2. `evals/report.py` and `evals/aggregate.py` SHALL NOT define, duplicate, or re-derive either.
   A second string literal `"FIXTURE-ONLY"` outside `evals/coverage.py` and its tests SHALL
   fail a unit test.
3. `SuiteReport` SHALL carry a `coverage` field holding the folded `CoverageReport` for the
   corpus it scored, and a `stamps: list[str]` field holding the computed stamps in a stable
   order.
4. The `NON-REPRESENTATIVE` stamp (`eval-methodology-alignment` R4.4) SHALL compose with the
   two stamps here rather than replace them. All three are orthogonal — corpus kind is *what
   the traces are*, `NON-REPRESENTATIVE` is *the corpus is too narrow*, `EVIDENCE-STARVED` is
   *the instruments could not see* — and a report SHALL show every stamp that applies.
5. Every stamp SHALL be a computed field with a test asserting the boundary condition. No stamp
   SHALL be satisfied by a sentence in a markdown file.

## R3 — Abstention is rendered wherever a rate is rendered

**User story.** As a reviewer, I want to see how many results a rate was computed from, so that
a denominator cannot quietly shrink to two.

Implements `eval-coverage` R3.1–R3.4 and R3.6 in the `SuiteReport` renderer. The criteria there
define the behavior; these define where it lands and what proves it.

### Acceptance criteria

1. `ScorecardCell` and `FailureModeIncidence` SHALL carry `na_count` and `n_decided`, and all
   four renderers — `report.json`, `report.md`, `report.html`, `summary.txt` — SHALL show both.
2. No renderer SHALL emit a percentage or a rate without displaying the denominator it was
   computed over, in the same cell or the adjacent one.
3. WHERE `n_decided < 10`, the renderer SHALL emit `n=<k>` and SHALL NOT emit a percentage or
   a confidence interval. A Wilson interval over four decided results is arithmetic performing
   a confidence it does not have.
4. `failure_mode_incidence` SHALL contain one row per **active** failure mode, including modes
   with zero incidence, each carrying a `liveness` field from `evals/coverage.py`. The 1.2.0
   report emits 10 rows for 17 active modes; a reader cannot currently distinguish "did not
   occur" from "nothing could see it".
5. Failure modes with `origin: hypothesis` SHALL be excluded from the active set and, WHERE
   shown at all, SHALL be rendered in a separate section labeled as unpromoted — consistent
   with `eval-coverage` R9. FM-019…FM-024 SHALL NOT appear in an incidence table.
6. The per-check abstention summary SHALL name the three checks contributing the most
   `not_applicable` results and their dominant reason code, so the single largest cause of
   abstention is visible without reading 1435 strings.

## R4 — A corpus is counted by distinct `trace_id`

**User story.** As a reader, I want `n` to mean the number of traces, because it is the
denominator under every rate in the report.

Implements `eval-coverage` R3.7–R3.8.

### Acceptance criteria

1. Tier A SHALL count its corpus by distinct `trace_id`. `evals/fixtures/traces/` holds 94
   files carrying **72 distinct ids**; `tier_a.load_fixture_traces` globs by filename and
   scores both copies of each of the 22 duplicates.
2. WHERE `n_files` and `n_distinct_traces` differ, the report SHALL name both.
3. Tier A's denominators and `TraceStore.rebuild_index` SHALL NOT disagree about the size of a
   corpus. `TraceStore.write` already refuses a duplicate id; the fixture loader SHALL adopt
   the same rule.
4. CI SHALL warn WHEN a fixture directory contains two files sharing a `trace_id`.
5. The 22 duplicated ids SHALL be named in the task record, and every `2 pass / 2 fail` row in
   the current report SHALL resolve to `1 pass / 1 fail` after this requirement lands. That
   collapse is the expected outcome, not a regression, and the baseline note SHALL say so.

## R5 — `na_reason` is a closed vocabulary, not a string

**User story.** As a maintainer, I want to aggregate abstentions by cause, because clustering
free text is how the current top-reasons table works and it is one rephrasing away from
splitting a cause in two.

Implements `eval-coverage` R3.5–R3.6.

### Acceptance criteria

1. `CheckResult` SHALL carry `na_reason: NaReason | None` drawn from the closed vocabulary
   `missing_span_type`, `missing_artifact`, `missing_raw_key`, `missing_scalar`,
   `not_in_scope`, alongside its existing human-readable `evidence_text`.
2. Every `not_applicable` result produced by a registered check SHALL set it. A unit test SHALL
   assert that no registered check can return `not_applicable` with `na_reason: None`.
3. `not_in_scope` SHALL be excluded from the `EVIDENCE-STARVED` denominator, per
   `eval-coverage` R11.1. A check declining a trace it was never meant to score is not
   blindness, and conflating the two is how `CHK-required-artifacts` produced 65 of 182
   headline failures.
4. `evals/coverage.py` SHALL aggregate by code and MAY keep the text sample as a secondary
   display. The code SHALL be the grouping key.
5. Adding the field SHALL NOT change any existing check's `outcome`. A task SHALL assert
   outcome-for-outcome equality against the committed report before and after.

## R6 — The headline and the verdict cannot outrun the instruments

**User story.** As a reader of CI, I want a green suite to be unable to claim more than it
measured, because a badge outlives every caveat in the prose around it.

Implements `eval-coverage` R2.4–R2.6 and R11.1–R11.3.

### Acceptance criteria

1. A report WHERE `not_applicable` exceeds 50% of all check results, excluding `not_in_scope`,
   SHALL carry `EVIDENCE-STARVED` naming the share and the three largest abstainers.
2. The headline SHALL name the count of `blind` and `unreachable` checks whenever either is
   non-zero, in the same sentence as the pass/fail counts.
3. WHERE any check is `unreachable`, the verdict SHALL render as `pass (instruments
   incomplete)` and SHALL NOT render as a bare `pass`. A blind check is a data state; an
   unreachable one is a code defect, and a green verdict over a code defect is the failure this
   criterion exists to prevent.
4. The corpus kind SHALL be shown adjacent to the liveness summary, so a fixture result cannot
   be read as a coverage claim.
5. CI SHALL print the liveness table on every Tier A run and SHALL NOT gate on it.
6. Threshold behavior SHALL be tested at 49.9% and 50.1%.

## R7 — Generic metrics are labeled as a sampling signal

**User story.** As a reader, I want an off-the-shelf metric to look like a way of choosing
traces to read, not like a quality result.

Implements `eval-methodology-alignment` R15.3.

### Acceptance criteria

1. `evals/metrics.py` output SHALL be rendered under a heading naming it a sampling signal.
2. No generic metric SHALL appear as a headline figure, in `summary.txt`, or in any CI summary
   line.
3. WHERE a generic metric is used to select traces for annotation, the sample manifest SHALL
   record which metric and threshold selected each trace, so a later reader can see the
   selection was not random and correct for it.

## R8 — Staleness is reported, never gated

**User story.** As the owner, I want to see how old the corpus and the annotations are without
asking, because the thing that decays silently is the thing that decays.

Implements `eval-methodology-alignment` R14.3–R14.4.

### Acceptance criteria

1. `index stats` SHALL report days since the most recent `AnnotationRecord`, the count of
   traces created since that record, and the newest and oldest trace timestamps.
2. `index stats` SHALL report, per R4 diversity floor, what the corpus is currently short by,
   naming the floor and the shortfall.
3. WHERE `evals/annotations/` is empty, the output SHALL say so explicitly rather than
   rendering a null or a zero. Zero annotations and a recent annotation are different states
   and SHALL be distinguishable at a glance.
4. Nothing in this requirement SHALL gate. Staleness is reported; the exit code is unchanged.
5. The output SHALL remain a single screen of plain text. This is the command the owner runs
   most and its value is that it costs nothing to read.

## R9 — The cadence is written down

**User story.** As the owner, I want the review rhythm recorded where the methodology is
recorded, because a loop with no period is a diagram, not a practice.

Implements `eval-methodology-alignment` R14.1–R14.2 and R15.4.

### Acceptance criteria

1. `docs/EVAL_METHODOLOGY.md` SHALL state the recurring review: ≥100 fresh traces open-coded
   every 2–4 weeks, and 10–20 outlier traces reviewed weekly between passes.
2. It SHALL state the event triggers that force a review regardless of calendar: the default
   model changes, a backend is added, or a harness component is enabled or disabled.
3. It SHALL carry a dated corpus-state table matching current `index stats` output, and a
   dated liveness table matching current `coverage liveness` output.
4. CI SHALL warn WHEN either table is more than 30 days older than the newest trace or the
   newest report. Warn, not fail.
5. The cadence SHALL be stated as a rhythm with a next date, not as an aspiration. "Every 2–4
   weeks" with no anchor date is unfalsifiable and SHALL NOT satisfy this requirement.

## R10 — Schema, baseline and determinism compatibility

**User story.** As a maintainer, I want this spec's fields to be additive, because the $0 gate
and its baseline are the only working part of the eval system today.

### Acceptance criteria

1. `SuiteReport.schema_version` SHALL be bumped to `2`, and a reader SHALL be able to load a
   version-1 report without error.
2. Every field added SHALL be deterministic. `tests/integration/evals/test_tier_a_integration.py`
   compares two runs of the same corpus to each other; that equality SHALL hold.
3. `evals/baselines/tier_a.json` records `check_outcomes` per check id and nothing derived from
   denominators, so the gate SHALL be unaffected by R3 and R4. A task SHALL verify this rather
   than assume it.
4. WHERE R4's distinct-id collapse changes a check's fixture outcome, the baseline SHALL be
   regenerated with a `reason` naming R4 as the cause.
5. `report_json_without_generated_at` SHALL remain the determinism comparator; no field added
   here SHALL carry a timestamp, a path outside the repo, a hostname, or an iteration-ordered
   collection.

## R11 — Test hygiene

**User story.** As a maintainer, I want this spec tested to the standard of the specs it
completes.

### Acceptance criteria

1. No test SHALL write to `evals/annotations/`, `evals/golden/`, or `evals/traces/`. Tests
   SHALL use `tmp_path` roots.
2. Every threshold and suppression path added here SHALL reach 100% branch coverage: the
   50% `EVIDENCE-STARVED` boundary, the `n_decided < 10` suppression, the `unreachable`
   verdict downgrade, the empty-annotations branch, and the doc-command audit.
3. The doc-command audit (R1.5) SHALL have a fixture proving it fires on the current
   `README.md:337` text and does not fire on a `docs/journal/` path.
4. Renderer changes SHALL be asserted against all four output formats, not only markdown. The
   HTML renderer is the one a reader opens and the one with no test today.

---

## Constraints

| | |
| --- | --- |
| Location | `evals/aggregate.py`, `evals/report.py`, `evals/coverage.py`, `evals/cli.py`, `evals/store.py`, `evals/checks/base.py`, `docs/`; no new package |
| Cost | **$0.00.** No task spends, and no task requires a key. |
| One implementation per stamp | R2. Corpus kind and `EVIDENCE-STARVED` are imported from `evals/coverage.py`, never re-derived |
| No vendor in the critical path | no Braintrust / LangSmith / Arize / DeepEval, consistent with the other four specs |
| Additive only | no existing check's `outcome` changes (R5.5); no existing requirement is restated |
| One gate | R1.5's doc-command audit. Liveness, staleness and stamps never gate |
| Evals never reach agents | unchanged from `eval-coverage` R14 |
| Renderer-enforced | every stamp is a computed field with a boundary test (R2.5) |

## Non-goals

- **Writing the telemetry.** `harness/telemetry.py` is `eval-methodology-alignment` Phase 1.
  This spec renders what the instruments report, including that they report nothing.
- **The re-index itself.** Making `output/runs/` primary is alignment task 2.4. R1 documents
  the correct path and gates the wrong one; it does not implement the parser.
- **The human annotation pass.** Alignment Phase 4, not delegable, and R8's staleness output
  exists to make its absence visible rather than to substitute for it.
- **Promoting FM-019…FM-024.** R3.5 keeps them out of incidence tables. Promotion requires an
  annotation record, per `eval-coverage` R9.
- **New checks.** Nothing here adds a detector. The claim is that the existing twenty become
  legible, not that there should be more of them.
- **A coverage dashboard.** Considered and rejected on 2026-09-14 for the same reason the
  workbench was built instead: an artifact about how starved the corpus is, in place of the
  reading that would unstarve it. The report and `index stats` are surfaces that already
  exist and are already read.
- **Multi-annotator κ.** A standing deviation, recorded in `eval-coverage`, not coverage.
