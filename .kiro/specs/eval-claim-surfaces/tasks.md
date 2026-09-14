# Tasks — Eval Claim Surfaces

**Spec ID:** `eval-claim-surfaces`
**Read first:** [`requirements.md`](./requirements.md), then [`design.md`](./design.md).

This file is a **living checklist**. Check a box only when its Definition of done is literally
true. Nothing in this spec spends money, so there are no human-triggered spend tasks to leave
open — but tasks 1.4 and 4.3 are blocked on work in another spec and stay open until it lands.

---

## How to execute this plan

One task per session. Do not start a second task before the first satisfies its Definition of
done and:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ evals/
uv run pytest tests/unit tests/integration/evals -q
```

Phases 1 and 3 are independent of everything. Phase 2 is internally sequential — `na_reason`
before the abstention summary, fields before renderers. Phase 4 runs after Phase 2.

**Cost for every task in this file: $0.00.**

---

## Phase 1 — The quickstart stops teaching the defect (free, no dependencies)

- [ ] **1.1 Caveat the two live quickstarts**
  - `README.md:337` and `evals/README.md:12` gain a one-line caveat naming the defect and
    linking `eval-methodology-alignment` task 2.4. Wording states what the command returns
    today (run workspaces, not run records) rather than describing it as broken.
  - **Definition of done:** neither snippet presents `--workspace-root ./workspace` without
    the caveat; a reader who runs it knows what they will get. No code changes.
  - _Requirements: R1.1, R1.3_

- [ ] **1.2 `scripts/audit_doc_commands.py`**
  - Per design §6. Scans tracked `*.md` outside the exemption paths for a corpus-building
    command resolving to `./workspace`; errors name file, line and owning task.
  - **Definition of done:** exits non-zero on the pre-1.1 `README.md` text, zero on the
    post-1.1 text, and zero on every path in `EXEMPT`.
  - _Requirements: R1.5, R1.4_

- [ ] **1.3 Wire the audit into the existing lint job**
  - `.github/workflows/ci.yml`, lint job. No new workflow, no new job.
  - **Definition of done:** the audit runs on every PR and fails the lint job on a match.
  - _Requirements: R1.5_

- [ ] **1.4 Correct the commands — BLOCKED on `eval-methodology-alignment` task 2.4**
  - Replace the caveated snippets with the corrected invocation against the run-record tree;
    remove the caveats added in 1.1.
  - **Definition of done:** every runnable corpus-building snippet in a non-exempt tracked doc
    invokes the run-record tree as primary source, and `index stats` after following the
    quickstart reports ≥3 backends. **Do not start before 2.4 lands** — writing a command for
    a parser that does not exist is the defect this spec is about.
  - _Requirements: R1.2_

- [ ] **1.5 Eval entry point in `GETTING_STARTED.md`**
  - Raise the eval link from a single line at `:180` to the same prominence as the harness and
    guardrail sections.
  - **Definition of done:** the link is reachable without scrolling past the harness section
    and lands on a page satisfying R1.2 or R1.3.
  - _Requirements: R1.6_

---

## Phase 2 — The report tells the truth (free, internally sequential)

- [ ] **2.1 `NaReason` vocabulary on `CheckResult`**
  - Add the closed `Literal` per design §4; make the parameter required in
    `evals/checks/base.py:82`'s `na(...)` constructor; update all twenty registered checks call site by
    call site.
  - **Definition of done:** no registered check can return `not_applicable` with
    `na_reason: None` (asserted by a test that walks the registry); an outcome-for-outcome diff
    against `evals/results/tierA_4671d49ae035_eb36475d7c/report.json` is **empty**.
  - _Requirements: R5.1, R5.2, R5.5_

- [ ] **2.2 `na_count` and `n_decided` on the aggregate models**
  - `ScorecardCell` and `FailureModeIncidence` per design §3. `n_decided = pass + fail` and is
    the only permitted denominator.
  - **Definition of done:** every rate in `report.json` carries both; no code path divides by
    anything else. Requires design §9.3's `static` flag to exist, provisional value acceptable.
  - _Requirements: R3.1, R3.2, coverage R3.1–R3.2_

- [ ] **2.3 Count by distinct `trace_id`**
  - `tier_a.load_fixture_traces` adopts `TraceStore.write`'s duplicate rule; report `n_files`
    and `n_distinct_traces` separately when they differ; CI warns on a fixture directory
    holding two files with one id.
  - **Definition of done:** the 22 duplicated ids are named in the commit message; Tier A
    denominators and `rebuild_index` agree on corpus size; every `2 pass / 2 fail` row resolves
    to `1 / 1`. That collapse is expected — see 4.1.
  - _Requirements: R4.1, R4.2, R4.3, R4.4, R4.5_

- [ ] **2.4 Renderer rules across all four formats**
  - `_rate_cell(rate, n_decided, na_count)` helper; no format string bypasses it; suppress
    percentage and CI under `n_decided < 10`. Resolve design §9.1 (does suppression extend to
    `summary.txt`) in this task.
  - **Definition of done:** no rendered percentage anywhere without its displayed denominator;
    the eleven incidence rows currently below `n=10` render `n=<k>` with no percentage and no CI;
    §9.1 is answered in the task record.
  - _Requirements: R3.1, R3.2, R3.3_

- [ ] **2.5 One row per active failure mode, carrying liveness**
  - Build the incidence table from the taxonomy loader rather than from observed results.
    Filter `origin: hypothesis` out of the active set; render unpromoted modes, if at all, in a
    separate labeled section.
  - **Definition of done:** the 1.2.0 corpus produces 17 rows, not 10; an FM nothing could see
    reads `liveness: unreachable` rather than being absent; FM-019…FM-024 appear in no
    incidence table.
  - _Requirements: R3.4, R3.5_

- [ ] **2.6 `AbstentionSummary` and the top-three abstainers**
  - Per design §3. Group by `na_reason` code, not by text. `not_in_scope` excluded from
    `n_na_in_scope`.
  - **Definition of done:** the largest cause of abstention is visible without reading 1435
    strings; `CHK-required-artifacts`'s 65 out-of-scope results no longer inflate the starvation
    share.
  - _Requirements: R3.6, R5.3, R5.4_

- [ ] **2.7 `SuiteReport.coverage` + `stamps`, imported not re-derived**
  - Fold the `CoverageReport` for the scored corpus onto the report; compose the three stamps
    in fixed order per design §2.1.
  - **Definition of done:** a Tier A fixture run renders `FIXTURE-ONLY`,
    `NON-REPRESENTATIVE` and `EVIDENCE-STARVED` together; the R2.2 test finds no second
    `"FIXTURE-ONLY"` literal outside `evals/coverage.py`; boundary tested at 49.9% / 50.1%.
  - _Requirements: R2.1, R2.2, R2.3, R2.4, R2.5, R6.1, R6.4, R6.6_

- [ ] **2.8 Headline and verdict cannot outrun the instruments**
  - Headline names abstention share and blind/unreachable counts; verdict renders
    `pass (instruments incomplete)` when any check is `unreachable`. Resolve design §9.2 in the
    task record.
  - **Definition of done:** a suite with one unreachable check cannot render a bare `pass`; the
    current run's headline names 1435 abstentions and 2 unreachable checks.
  - _Requirements: R6.2, R6.3_

- [ ] **2.9 CI prints the liveness table; never gates on it**
  - `coverage liveness` runs in the `eval-tier-a` job and writes to the step summary.
  - **Definition of done:** the table appears on every Tier A run; the job's exit code is
    unchanged by it.
  - _Requirements: R6.5_

- [ ] **2.10 Demote generic metrics**
  - `evals/metrics.py` output rendered under a heading naming it a sampling signal; absent from
    every headline, `summary.txt` line and CI summary.
  - **Definition of done:** no generic metric appears as a headline figure; a sample manifest
    that used a metric to select traces records which metric and threshold.
  - _Requirements: R7.1, R7.2, R7.3_

- [ ] **2.11 HTML renderer: stamps, abstention column, dark mode**
  - Per design §5.1. Stamp row under the headline; `not_applicable` as a column in both tables;
    `prefers-color-scheme` block. No new dependency, no CDN. Drop the dark-mode half if it
    slows the phase (design §9.4).
  - **Definition of done:** the HTML report shows every stamp and both denominators, renders
    legibly in both themes, and has assertions — it has none today.
  - _Requirements: R3.1, R3.2, R11.4_

---

## Phase 3 — The clock (free, no dependencies)

- [ ] **3.1 `index stats` staleness and floor shortfall**
  - Header block per design §7: corpus size with distinct-id count, span, per-floor shortfall,
    annotation staleness, next-pass state. Two new store methods; consume alignment's
    `CorpusProfile` if present, compute inline if not.
  - **Definition of done:** output fits one screen; empty annotations render `NONE` and never
    `0 days`; every R4 floor names its shortfall; exit code unchanged.
  - _Requirements: R8.1, R8.2, R8.3, R8.4, R8.5_

- [ ] **3.2 Cadence written into `EVAL_METHODOLOGY.md`**
  - The table from design §7.1: open coding every 2–4 weeks, weekly outlier review, the three
    event triggers, and the honest anchor.
  - **Definition of done:** the cadence is a rhythm with a stated anchor dependency, not an
    aspiration; the three event triggers are named.
  - _Requirements: R9.1, R9.2, R9.5_

- [ ] **3.3 Dated corpus-state and liveness tables**
  - `EVAL_METHODOLOGY.md` carries both, each matching current command output, each dated.
  - **Definition of done:** both tables reproduce the current `index stats` and
    `coverage liveness` output; both carry a date.
  - _Requirements: R9.3_

- [ ] **3.4 CI staleness warning on the dated tables**
  - Warn when either table is more than 30 days older than the newest trace or newest report.
  - **Definition of done:** the warning fires on a deliberately stale table and does not fail
    the build.
  - _Requirements: R9.4, R8.4_

---

## Phase 4 — Compatibility and closing the loop (free, after Phase 2)

- [ ] **4.1 Baseline regeneration with a reason naming R4**
  - Re-run Tier A, accept the baseline, and write a `reason` stating that the distinct-id
    collapse changed fixture denominators and why that is expected.
  - **Definition of done:** `evals/baselines/tier_a.json` is current; its `reason` names R4 as
    the cause; the gate is green against it.
  - _Requirements: R10.3, R10.4, R4.5_

- [ ] **4.2 Determinism and schema compatibility verified, not assumed**
  - Confirm `test_tier_a_two_runs_deterministic` still holds; confirm a version-1 report loads;
    confirm no added field carries a timestamp, external path, hostname, or iteration-ordered
    collection.
  - **Definition of done:** the integration test passes; a stored version-1 fixture report
    loads without error; the field audit is recorded in the task note.
  - _Requirements: R10.1, R10.2, R10.5_

- [ ] **4.3 Branch coverage on every threshold added here**
  - The 50% boundary, the `n_decided < 10` suppression, the `unreachable` downgrade, the
    empty-annotations branch, and the doc audit's fire/no-fire pair.
  - **Definition of done:** 100% branch coverage on those paths; no test writes to
    `evals/annotations/`, `evals/golden/` or `evals/traces/`.
  - _Requirements: R11.1, R11.2, R11.3_

- [ ] **4.4 Correct the claims this spec's output invalidates**
  - `evals/taxonomy/COVERAGE.md`'s *"every check-detected FM has a named implementation"*
    gains how many of those implementations have ever decided anything. Same pass over
    `docs/HARNESS.md`'s `enforced` column and `README.md`'s taxonomy paragraph.
  - **Definition of done:** no tracked document claims coverage on the strength of check
    registration; every such claim cites liveness instead.
  - _Requirements: R6.4, coverage R11.5, coverage R11.6_

- [ ] **4.5 Journal entry**
  - `docs/journal/2026-09-<dd>-claim-surfaces.md` in house style: what was found, what was
    built, what did not change, what the next session starts with.
  - **Definition of done:** entry exists, is linked from `docs/journal/README.md`, and states
    plainly that the corpus and the annotation count are unchanged by this spec.
  - _Requirements: R9.3_

- [ ] **4.6 Update `EVALS_ROADMAP.md` and the four sibling spec READMEs**
  - One line each: this spec exists, what it owns, and that the tasks it sequences in alignment
    Phase 8 and coverage Phase 4 are executed here rather than there.
  - **Definition of done:** no reader of alignment 8.1–8.4 or coverage 4.1–4.6 can be unsure
    which spec owns execution; no requirement text is duplicated.
  - _Requirements: R2.1_

---

## Minimum defensible slice

**Phase 1, plus tasks 2.1, 2.2 and 3.1.** The quickstart stops teaching the defect, every rate
carries its decided denominator, and the corpus has a staleness reading. Half a day, no schema
migration, no baseline regeneration.

If even that is too long: **task 1.1.** Two lines of markdown. It is the only item across the
five eval specs whose cost is minutes and whose effect is that the next person to clone this
repo does not reproduce, on their first command, the defect that took two months to find.
