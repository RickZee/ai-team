# Requirements — Eval Harness

**Spec ID:** `eval-harness`
**Status:** Draft for implementation
**Owner:** Rick Zakharov
**Target repo:** `ai-team` (in-place extension of `evals/`)
**Created:** 2026-08-16

---

## Introduction

`ai-team` runs a nine-agent software engineering team across three orchestration
backends (CrewAI, LangGraph, Claude Agent SDK). It already has a *measurement*
layer: `evals/fixtures.py` (`EvalResult`, `LLMJudge`, `EnsembleJudge`),
`evals/metrics.py` (`compute_metrics`, `format_scorecard`), `evals/run_evals.py`
(parallel per-backend runner with watchdogs), eight scenario contracts in
`evals/scenarios/`, and `src/ai_team/guardrails/corpus_metrics.py`
(precision/recall accounting for guardrails).

What it does **not** have is a *methodology* layer. Specifically:

1. **No trace corpus.** Runs emit `logs/phases.jsonl`, `logs/costs.jsonl`,
   `logs/audit.jsonl` and `logs/session.json` into per-run workspaces, plus SQLite
   run history in `src/ai_team/core/run_store.py`. Nothing unifies these into a
   queryable, versioned corpus you can sample from.
2. **No error analysis loop.** `docs/posts/failure-taxonomy.md` documents ten real
   failure classes with root causes and shipped fixes — but it was written from
   memory, not derived from coded traces, and no eval is mechanically linked to it.
3. **No human labels and therefore no judge validation.** `compute_metrics()` sets
   `judge_provisional = True` when the judge is single-vendor, which is honest but
   unresolved: nobody knows this judge's true positive rate. Every judge-derived
   number in `docs/COMPARISON_RESULTS.md` is currently unfalsifiable.
4. **Judges emit continuous scores compared against thresholds** (`score >= 0.7`),
   which is the failure mode binary grading exists to prevent.
5. **Judge prompts are inline class constants** — unversioned, undiffable, so
   "the score moved" cannot be attributed to a system change vs. a prompt change.
6. **No regression gate.** Evals are run by hand. CI (`.github/workflows/ci.yml`)
   runs lint / unit / web-e2e / integration / security — no eval job.
7. **No replay.** Every eval invocation costs money and produces a different
   answer, so evals cannot run per-PR.
8. **No reliability metric.** `pass@k` / `pass^k` appear in `docs/EVALS.md` §12 as
   sketches; `metrics.py` has no k-run support.

This spec closes those gaps. It follows the error-analysis-first methodology
(Husain & Shankar): **traces → open coding → axial coding → failure taxonomy →
cheap deterministic checks where possible → validated binary judges where not →
bias-corrected rates → regression gate.**

### Design constraints (decided)

| Constraint | Decision |
| --- | --- |
| Location | Extend `evals/` in-repo; no new repo. Keep a clean adapter boundary so it stays extractable. |
| Emphasis | Depth over breadth. Method first, applied to the failure modes already observed. Role-eval breadth (`docs/EVALS.md` §13) is explicitly out of scope for v1. |
| Budget | **≤ $5.00 USD of model spend for one full live suite run.** Per-PR tier must be **$0.00**. |
| Judge stack | Home-grown. No DeepEval / Braintrust / LangSmith dependency in the critical path; optional export only. |
| Backwards compatibility | `evals/run_evals.py --compare` and the three `evals/backends/test_*_eval.py` files must keep working throughout. |

### Non-goals (v1)

- Role-specific evals for DevOps / IaC / QA / security / architecture agents
  (`docs/EVALS.md` §13). The harness must make them cheap to add; v1 does not add them.
- Online / production evaluation of live user traffic.
- Multi-annotator workflows. One domain expert ("benevolent dictator") is the
  labeling authority.
- Replacing the existing pytest-based backend eval files. They become clients of
  the new check registry, not casualties of it.
- Fine-tuning or training any model.

### Glossary

| Term | Definition |
| --- | --- |
| **Run** | One backend executing one scenario once, producing one workspace. |
| **Trace** | The normalized, immutable event record of a Run, assembled from its JSONL logs and result object. |
| **Span** | One event within a Trace (phase transition, tool call, guardrail check, LLM call, retry, error). |
| **Labeling unit** | A `(trace_id, span_id | "run", failure_mode_id)` triple that a human marks present/absent. The atom of the golden dataset. |
| **Check** | A deterministic, code-only predicate over a Trace. Cheap, exact, no model call. |
| **Judge** | A binary LLM classifier over evidence extracted from a Trace. Expensive, approximate, must be validated. |
| **Failure mode (FM)** | A named, versioned category in the taxonomy, e.g. `FM-001 tool_call_omission`. |
| **Golden set** | Human-labeled labeling units, split into `dev` and `test`, used to align and validate Judges. |
| **Alignment** | Measured agreement of a Judge with human labels: TPR, TNR, Cohen's κ. |
| **Tier A / B / C** | Execution tiers: A = offline replay (PR, $0), B = live smoke (nightly, ≤$2), C = full matrix (manual/weekly, ≤$5). |

---

## Requirements

### R1 — Trace capture and normalization

**User story:** As an eval engineer, I want every run of any backend to produce one
normalized, immutable trace file, so that scoring is decoupled from execution and I
can analyze runs long after they finished.

**Acceptance criteria**

1.1 WHEN a run completes, aborts, or is killed by a watchdog, THE SYSTEM SHALL write
exactly one trace document to `evals/traces/<trace_id>.json`.

1.2 THE SYSTEM SHALL derive traces from artifacts already written by the backends —
`logs/phases.jsonl`, `logs/costs.jsonl`, `logs/audit.jsonl`, `logs/session.json`,
the workspace file tree, and the backend's result dict — and SHALL NOT require new
instrumentation inside `src/ai_team/backends/*` for v1.

1.3 THE SYSTEM SHALL assign `trace_id = f"{scenario_id}__{backend}__{utc_iso_compact}__{short_uuid}"`,
unique across concurrent runs.

1.4 A trace document SHALL contain, at minimum: `schema_version`, `trace_id`,
`scenario_id`, `backend`, `git_sha`, `started_at`, `ended_at`, `status`,
`model_ids` (per role), `spans[]`, `artifacts` (workspace file inventory with sizes
and sha256), `cost` (`usd`, `input_tokens`, `output_tokens`, `source`), and
`provenance` (see R14).

1.5 Each span SHALL contain `span_id`, `parent_span_id | null`, `type`, `t_start`,
`t_end`, `agent_role | null`, `phase | null`, and a `payload` dict, where `type` is
one of: `phase_start`, `phase_end`, `llm_call`, `tool_use`, `tool_result`,
`guardrail_check`, `retry`, `error`, `human_interrupt`, `spend_event`,
`smoke_probe`, `subagent_start`, `subagent_stop`.

1.6 WHEN a source log is missing, malformed, or truncated, THE SYSTEM SHALL still
emit a trace, record the gap in `trace.warnings[]`, and SHALL NOT raise.

1.7 Trace documents SHALL be append-only in practice: once written, THE SYSTEM SHALL
refuse to overwrite an existing `trace_id` file and SHALL error loudly instead.

1.8 THE SYSTEM SHALL provide `evals.trace.from_workspace(workspace_dir, ...) -> Trace`
that can retroactively build a trace from any historical workspace under
`./workspace/`, so the existing run history becomes corpus without re-spending.

---

### R2 — Trace corpus, indexing and sampling

**User story:** As an eval engineer, I want to query and sample the trace corpus,
so that error analysis operates on a representative set rather than whatever run I
happen to remember.

**Acceptance criteria**

2.1 THE SYSTEM SHALL maintain a SQLite index at `evals/traces/index.db` with one row
per trace, denormalizing: `trace_id`, `scenario_id`, `backend`, `status`, `git_sha`,
`started_at`, `duration_s`, `cost_usd`, `span_count`, `error_count`,
`retry_count`, `file_count`, `label_count`.

2.2 THE SYSTEM SHALL rebuild the index idempotently from `evals/traces/*.json` via
`python -m evals.cli index rebuild`.

2.3 THE SYSTEM SHALL support sampling strategies selectable by flag:
`random`, `stratified` (by `backend` × `scenario_id` × `status`), `extremes`
(longest / costliest / most-retried), `failed-only`, and `unlabeled`.

2.4 WHEN `stratified` sampling is requested and a stratum has fewer traces than its
quota, THE SYSTEM SHALL fill the shortfall from the largest stratum and record the
imbalance in the sample manifest.

2.5 THE SYSTEM SHALL write every sample to `evals/samples/<sample_id>.json` recording
the strategy, seed, filters, and resulting `trace_id` list, so any analysis is
reproducible.

2.6 THE SYSTEM SHALL support `--seed` on all sampling commands and SHALL produce
identical samples for identical `(seed, strategy, filters, corpus_state_hash)`.

---

### R3 — Annotation workflow (open coding)

**User story:** As the domain expert, I want to review traces and write free-text
notes fast, so that the failure taxonomy comes from evidence rather than from my
recollection.

**Acceptance criteria**

3.1 THE SYSTEM SHALL provide `python -m evals.cli annotate --sample <sample_id>`
which presents traces one at a time in the terminal.

3.2 For each trace THE SYSTEM SHALL render a compact review view: scenario
description, status, phase timeline with durations, retry and error spans, guardrail
firings, spend total, workspace file tree, and the first 60 lines of any
`docs/security_report.md` / test output present.

3.3 THE SYSTEM SHALL accept for each trace: a free-text note, an optional
`first_failure_span_id` (the *first upstream* failure, not downstream cascade), and
zero or more provisional tags.

3.4 THE SYSTEM SHALL persist annotations to `evals/annotations/<annotator>.jsonl`,
one JSON object per line, never rewriting prior lines.

3.5 THE SYSTEM SHALL support resuming an interrupted annotation session, skipping
already-annotated `trace_id`s.

3.6 THE SYSTEM SHALL report, at session end, how many consecutive traces produced no
new provisional tag, so the expert can judge **theoretical saturation** (target: 20
consecutive traces with no new tag).

3.7 THE SYSTEM SHALL NOT show any LLM-generated suggestion during open coding.
Anchoring the human on a model's guess corrupts the ground truth the whole harness
rests on.

---

### R4 — Failure taxonomy (axial coding)

**User story:** As an eval engineer, I want a single versioned taxonomy file that
every check, judge, and report references by ID, so that "what we measure" and
"what actually breaks" cannot silently drift apart.

**Acceptance criteria**

4.1 THE SYSTEM SHALL store the taxonomy at `evals/taxonomy/failure_modes.yaml`.

4.2 Each entry SHALL have: `id` (`FM-###`), `slug`, `title`, `definition`
(one paragraph, decidable by a human without further context), `layer`
(`model` | `framework` | `harness` | `provider`), `severity`
(`blocker` | `major` | `minor`), `detection` (`check` | `judge` | `manual`),
`positive_examples[]` and `negative_examples[]` (each a `trace_id` + `span_id`),
`introduced_in` (taxonomy version), and `status` (`active` | `retired`).

4.3 THE SYSTEM SHALL seed the taxonomy with the ten failure classes already
documented in `docs/posts/failure-taxonomy.md`, preserving their observed layer
attribution:

| ID | Slug | Layer | Source |
| --- | --- | --- | --- |
| FM-001 | `tool_call_omission` | model | taxonomy §1 — code emitted as prose, workspace empty |
| FM-002 | `self_triggering_retry_loop` | framework | §2 — listener re-triggers itself; 93,284 iterations |
| FM-003 | `runtime_coupling_starvation` | harness | §3 — spinning thread starves GIL; 78-min interrupt delay |
| FM-004 | `run_id_collision` | harness | §4 — TOCTOU on run-id allocation |
| FM-005 | `guardrail_false_positive` | harness | §5 — lexical scope guardrail rejects correct test code |
| FM-006 | `runtime_verification_gap` | harness | §6 — 70/70 tests green, app returns HTTP 500 |
| FM-007 | `unbounded_spend` | harness | §7 — retry loop is also a billing loop |
| FM-008 | `metric_source_drift` | harness | §8 — dashboard reports null cost / 0 files during real runs |
| FM-009 | `provider_dialect_mismatch` | provider | §9 — Vertex adapter rejects tool-call ids; 133 errors/run |
| FM-010 | `gate_environment_mismatch` | harness | §10 — gate venv lacks generated `requirements.txt` deps |

4.4 THE SYSTEM SHALL validate the taxonomy on load: unique IDs, every `layer` /
`severity` / `detection` value in its enum, every referenced `trace_id` resolvable in
the corpus, and every `positive_examples` entry non-empty for any FM whose
`detection` is `judge`.

4.5 WHEN a failure mode is retired, THE SYSTEM SHALL keep its entry with
`status: retired` and a `retired_reason`, and SHALL NOT reuse its ID.

4.6 THE SYSTEM SHALL emit `evals/taxonomy/COVERAGE.md` on demand: every FM, its
detection mechanism, the check or judge that implements it, its label count, and its
current measured rate — so an uncovered failure mode is visible rather than forgotten.

4.7 THE SYSTEM SHALL support taxonomy evolution: `python -m evals.cli taxonomy propose --from-annotations`
clusters open-coding notes and proposes candidate new FMs for human acceptance. The
human accepts or rejects; THE SYSTEM SHALL NOT auto-add.

---

### R5 — Deterministic checks

**User story:** As an eval engineer, I want every failure mode that *can* be detected
by code to be detected by code, so that model spend and judge uncertainty are
reserved for the genuinely subjective questions.

**Acceptance criteria**

5.1 THE SYSTEM SHALL define a `Check` protocol: `id`, `failure_mode_id`, `tier`,
and `run(trace: Trace) -> CheckResult`, where `CheckResult` carries
`outcome` (`pass` | `fail` | `not_applicable`), `evidence` (list of `span_id` plus a
human-readable string), and `detail` (dict).

5.2 Checks SHALL be pure functions of a Trace: no network, no filesystem writes, no
model calls. THE SYSTEM SHALL enforce this in tests by running the full check suite
with network access disabled.

5.3 THE SYSTEM SHALL implement at minimum these checks, each bound to its FM:

| Check ID | FM | Predicate (fails when…) |
| --- | --- | --- |
| `CHK-tool-call-emitted` | FM-001 | a development phase completed with zero `tool_use` spans, or with fenced code in an assistant message and no corresponding file artifact |
| `CHK-phase-repeat-bounded` | FM-002 | any `(phase, agent_role)` pair has more `phase_start` spans than `scenario.max_phase_repeats` (default 4) |
| `CHK-listener-self-trigger` | FM-002 | static introspection finds a CrewAI flow method that `@listen`s its own name (port of the existing meta-test into the registry) |
| `CHK-interrupt-latency` | FM-003 | elapsed between a `human_interrupt` span and its surfacing event exceeds `max_interrupt_latency_s` (default 60) |
| `CHK-workspace-isolation` | FM-004 | two traces in the same suite run resolve to the same `workspace_dir` |
| `CHK-guardrail-fp-budget` | FM-005 | guardrail `fail` spans on a run that otherwise met all acceptance criteria exceed 0 |
| `CHK-runtime-smoke-present` | FM-006 | a run reports `status == complete` with no `smoke_probe` span, or with a failing one |
| `CHK-spend-ceiling` | FM-007 | `cost.usd > scenario.budget_usd_max`, or a `spend_event` shows the guard failing to abort past ceiling |
| `CHK-metric-source-agreement` | FM-008 | artifact-derived file count / cost disagrees with event-derived values by more than tolerance |
| `CHK-provider-error-rate` | FM-009 | HTTP 4xx provider errors per run exceed `max_provider_errors` (default 0 for a green run) |
| `CHK-gate-env-fidelity` | FM-010 | any test span failed with `ModuleNotFoundError` for a package listed in the generated `requirements.txt` |
| `CHK-required-artifacts` | — | scenario `expected.files` not all present |
| `CHK-hallucination-density` | — | `count_hallucinations()` per generated file exceeds threshold |

5.4 THE SYSTEM SHALL register checks by decorator into a single registry so adding a
check requires no edits to the runner.

5.5 THE SYSTEM SHALL run all applicable checks in under 5 seconds for a corpus of
200 traces on a laptop.

5.6 WHEN a scenario does not exercise a check's precondition, THE CHECK SHALL return
`not_applicable` rather than `pass`. Aggregation SHALL exclude `not_applicable` from
denominators.

---

### R6 — Guardrail classifier evaluation

**User story:** As an eval engineer, I want the project's guardrails scored as the
classifiers they are, so that "I lowered the false-positive rate" is a measured
claim, per the lesson in taxonomy §5.

**Acceptance criteria**

6.1 THE SYSTEM SHALL maintain a labeled guardrail corpus at
`evals/corpora/guardrails/<guardrail_name>.jsonl`, each record carrying `case_id`,
`input` (the exact payload the guardrail receives), `label` (`violation` |
`benign`), `source` (`observed` | `synthetic`), and `origin_trace_id` where observed.

6.2 THE SYSTEM SHALL seed the corpus with the real false positives recorded in
taxonomy §5 — pytest test bodies containing *test, coverage, suite, validation*, and
`tests/conftest.py` — labeled `benign`.

6.3 THE SYSTEM SHALL score each guardrail against its corpus using the existing
`src/ai_team/guardrails/corpus_metrics.py` (`ConfusionCounts`, `score`,
`format_report`) and SHALL NOT reimplement confusion accounting.

6.4 THE SYSTEM SHALL require a minimum corpus size of 40 cases per guardrail with at
least 15 of each label before its metrics may gate anything; below that, metrics are
reported as `provisional`.

6.5 THE SYSTEM SHALL fail the guardrail eval WHEN, for any scored guardrail, recall
drops below its configured floor or false-positive rate rises above its configured
ceiling, both declared in `evals/corpora/guardrails/thresholds.yaml`.

6.6 THE SYSTEM SHALL sweep any threshold-parameterized guardrail across its parameter
range and emit the precision/recall curve to the run report, so threshold changes are
argued from a curve rather than from one batch's readings.

6.7 The guardrail eval SHALL cost $0.00 and run in Tier A.

---

### R7 — Binary, versioned LLM judges

**User story:** As an eval engineer, I want judges that answer one binary question
from a file-based, versioned prompt, so that a moving score is attributable to a
system change rather than to an invisible prompt edit.

**Acceptance criteria**

7.1 Every judge SHALL answer exactly one binary question about one failure mode or
one acceptance criterion. THE SYSTEM SHALL reject a judge definition whose rubric
declares more than one decision.

7.2 Judge prompts SHALL live in `evals/judges/prompts/<judge_id>.v<N>.md` as git-
tracked files with front matter: `judge_id`, `version`, `failure_mode_id`,
`question`, `pass_means`, `fail_means`, `model`, `provider`, `evidence_builder`.

7.3 THE SYSTEM SHALL compute `prompt_hash = sha256(prompt_file_bytes)` and record it
on every verdict. WHEN the prompt file changes, THE SYSTEM SHALL require the version
number to increment, and SHALL fail validation otherwise.

7.4 Judges SHALL return `{"verdict": "pass"|"fail", "reason": str, "evidence_quote": str}`.
THE SYSTEM SHALL NOT accept a numeric score field. Existing continuous
`LLMJudge.check()` SHALL remain available for legacy callers but SHALL be marked
deprecated and excluded from gating.

7.5 THE SYSTEM SHALL retain the provider-independence machinery already in
`evals/fixtures.py`: `AI_TEAM_JUDGE_PROVIDER`, `AI_TEAM_JUDGE_MODEL`, and
`EnsembleJudge` with its `spread` / `contested` / `single_vendor` reporting.

7.6 WHEN the backend under evaluation and the judge share a vendor, THE SYSTEM SHALL
mark the verdict `single_vendor: true` and SHALL exclude it from any published
cross-backend comparison unless a second-vendor judge agrees.

7.7 THE SYSTEM SHALL cache verdicts keyed by
`sha256(prompt_hash + model_id + evidence_bytes)` in `evals/judges/cache/`, so a
re-scored trace with unchanged evidence and unchanged prompt costs $0.00.

7.8 THE SYSTEM SHALL make evidence construction explicit and deterministic: each
judge names an `evidence_builder` function that maps a Trace to a bounded string
(default cap 4,000 characters), and the evidence bytes SHALL be recorded with the
verdict.

7.9 WHEN a judge call fails after 3 attempts, THE SYSTEM SHALL record
`verdict: "error"`, SHALL exclude it from rate computation, and SHALL surface the
error count in the report — never silently coercing an error to `fail`.
*(This corrects current behaviour in `LLMJudge.check()`, which returns
`passed=False` on error and therefore inflates measured failure rates.)*

---

### R8 — Judge alignment and bias correction

**User story:** As an eval engineer, I want to know each judge's true positive and
true negative rate against my own labels, so that I can answer "how do you know your
judge is right?" with a number and correct the rates it reports.

**Acceptance criteria**

8.1 THE SYSTEM SHALL maintain a golden set at `evals/golden/<failure_mode_id>.jsonl`,
each record: `labeling_unit_id`, `trace_id`, `span_id | "run"`, `failure_mode_id`,
`human_label` (`present` | `absent`), `annotator`, `labeled_at`, `notes`,
`split` (`dev` | `test`).

8.2 THE SYSTEM SHALL require ≥ 100 labeled units per judge before that judge may
gate, with ≥ 30 of the minority class. Below that, the judge is `advisory` only.

8.3 THE SYSTEM SHALL assign splits once, deterministically
(`split = "test" if sha256(labeling_unit_id) % 100 < 40 else "dev"`), stratified so
each split holds ≥ 25% of each class, and SHALL persist the assignment. Re-splitting
SHALL require an explicit `--force-resplit` flag and SHALL be logged.

8.4 THE SYSTEM SHALL forbid judge-prompt iteration against the `test` split. Running
`evals.cli judge align` SHALL read only `dev`; running `evals.cli judge validate`
SHALL read only `test` and SHALL refuse to run more than once per `prompt_hash`
without `--allow-retest` (recorded in the report as a multiple-comparisons warning).

8.5 THE SYSTEM SHALL report, per judge, on the `test` split: TP, FP, TN, FN, TPR
(recall on `present`), TNR (specificity), precision, F1, accuracy, Cohen's κ, and
95% bootstrap confidence intervals (2,000 resamples) for TPR and TNR.

8.6 A judge SHALL be eligible to gate only WHEN `TPR ≥ 0.90` AND `TNR ≥ 0.90` AND
`κ ≥ 0.70` on the held-out `test` split with n ≥ 100. THE SYSTEM SHALL enforce this
mechanically; an ineligible judge's verdicts are recorded and reported but do not
affect exit status.

8.7 THE SYSTEM SHALL report bias-corrected failure rates. Given observed judge
positive rate `p̂` and validated `TPR`/`TNR`, THE SYSTEM SHALL compute
`p = (p̂ + TNR − 1) / (TPR + TNR − 1)`, clamped to `[0, 1]`, and SHALL present both
raw and corrected rates side by side with the correction's confidence interval.
WHEN `TPR + TNR − 1 ≤ 0.2`, the correction is unstable and THE SYSTEM SHALL suppress
the corrected figure with an explanation rather than print a misleading number.

8.8 THE SYSTEM SHALL emit a per-judge disagreement report listing every `test`-split
unit where judge and human differ, with the judge's stated reason, so alignment work
targets real confusions.

8.9 THE SYSTEM SHALL re-validate every judge WHEN its prompt version changes, its
model id changes, or 30 days elapse — and SHALL mark stale validations in reports.

---

### R9 — Reliability under non-determinism

**User story:** As an eval engineer, I want to distinguish "the system can do this"
from "the system reliably does this", so that a lucky single run cannot be reported
as a capability.

**Acceptance criteria**

9.1 THE SYSTEM SHALL support running a scenario × backend `k` times and SHALL compute
`pass@k` (≥ 1 success), `pass^k` (all k succeed), and `pass_rate` (successes / k).

9.2 THE SYSTEM SHALL default to `k = 3` in Tier B and `k = 1` in Tier A, configurable
per scenario.

9.3 THE SYSTEM SHALL flag a scenario × backend cell as `flaky` WHEN
`0 < pass_rate < 1`, and SHALL list flaky cells prominently in the report — a flaky
cell is a finding, not a footnote.

9.4 THE SYSTEM SHALL report a Wilson score 95% confidence interval on `pass_rate`
and SHALL display `n` alongside every rate. No rate SHALL be printed without its `n`.

9.5 THE SYSTEM SHALL NOT report a difference between two backends as meaningful
WHEN their `pass_rate` confidence intervals overlap; the report SHALL say
"indistinguishable at n=k" instead.

---

### R10 — Cost, latency and budget accounting

**User story:** As an eval engineer, I want every run's true cost recorded regardless
of backend, and a hard ceiling on suite spend, so that the eval system cannot itself
become the billing loop described in taxonomy §7.

**Acceptance criteria**

10.1 THE SYSTEM SHALL record `cost.usd` for every trace with an explicit `source`:
`sdk_reported` (Claude Agent SDK `total_cost_usd`), `provider_usage`
(OpenRouter `usage.cost` / LiteLLM `response_cost`), `token_estimate`, or `unknown`.

10.2 WHEN a backend reports no cost, THE SYSTEM SHALL estimate from token counts and
a rate table at `evals/pricing.yaml`, and SHALL mark `source: token_estimate`.
Estimated costs SHALL NOT be compared against reported costs without the disparity
being flagged. *(Today CrewAI and LangGraph traces have `cost_usd = None`, which
silently drops them from budget checks.)*

10.3 THE SYSTEM SHALL enforce a suite-level hard ceiling, default $5.00, configurable
via `AI_TEAM_EVAL_BUDGET_USD`. WHEN cumulative measured spend crosses the ceiling,
THE SYSTEM SHALL abort remaining runs, mark them `skipped_budget`, and exit non-zero.

10.4 THE SYSTEM SHALL record per-phase wall time and SHALL report p50 / p95 latency
per backend per scenario.

10.5 THE SYSTEM SHALL report cost-per-successful-run (`total_spend / successes`)
alongside raw cost, since a cheap backend that fails is not cheap.

10.6 THE SYSTEM SHALL print a projected cost before executing a live tier and SHALL
require `--yes` (or `CI=true`) to proceed when the projection exceeds 50% of the
ceiling.

---

### R11 — Offline replay tier

**User story:** As an eval engineer, I want a tier that scores recorded traces with
zero model spend and deterministic output, so that evals can run on every pull
request.

**Acceptance criteria**

11.1 THE SYSTEM SHALL maintain a committed, version-controlled fixture corpus at
`evals/fixtures/traces/` containing a curated set of traces (target 40–60) that
covers every active failure mode with at least one positive and one negative example.

11.2 Fixture traces SHALL be redacted: no API keys, no absolute home paths, no
personal identifiers. THE SYSTEM SHALL run a redaction linter over them in CI.

11.3 Tier A SHALL execute: all deterministic checks (R5), the guardrail corpus eval
(R6), judge verdicts served **exclusively from cache** (R7.7), and all aggregation
and reporting.

11.4 WHEN a Tier A judge verdict is not present in cache, THE SYSTEM SHALL fail the
run with an actionable message naming the missing key, rather than making a network
call. Tier A network egress for model APIs SHALL be blocked in tests.

11.5 Tier A SHALL be bit-for-bit deterministic: two consecutive invocations on the
same commit SHALL produce byte-identical `report.json` apart from a single
`generated_at` field.

11.6 Tier A SHALL complete in under 120 seconds on GitHub-hosted `ubuntu-latest`.

11.7 THE SYSTEM SHALL provide `python -m evals.cli cache warm --tier B` to populate
the judge cache from a live run, so Tier A stays honest as the corpus grows.

---

### R12 — Regression gate and CI integration

**User story:** As a maintainer, I want a pull request to fail when it makes the
system measurably worse, so that reliability is defended automatically rather than
remembered occasionally.

**Acceptance criteria**

12.1 THE SYSTEM SHALL maintain a baseline at `evals/baselines/<tier>.json` recording,
per metric, the last accepted value, the commit that set it, and the date.

12.2 THE SYSTEM SHALL compare a run's report to the baseline and SHALL fail WHEN any
of the following regress beyond tolerance:

| Metric | Gate |
| --- | --- |
| Any deterministic check that passed in baseline | now fails → **fail** |
| Guardrail recall (per guardrail) | drops below floor in `thresholds.yaml` → **fail** |
| Guardrail false-positive rate | rises above ceiling → **fail** |
| Gating-eligible judge failure rate (bias-corrected) | rises by > 5 percentage points → **fail** |
| Suite `pass^k` | drops → **fail** |
| Suite cost | rises by > 25% → **warn**; exceeds ceiling → **fail** |
| p95 latency | rises by > 50% → **warn** |

12.3 Verdicts from judges that are not gating-eligible (R8.6) SHALL NOT contribute to
pass/fail, only to the report.

12.4 THE SYSTEM SHALL provide `python -m evals.cli baseline accept --tier <t> --reason <text>`
which updates the baseline and requires a reason string, recorded in the file.

12.5 THE SYSTEM SHALL add a GitHub Actions job `eval-tier-a` to
`.github/workflows/ci.yml`, running on every pull request, requiring no secrets, and
uploading `report.json` + `report.md` as artifacts.

12.6 THE SYSTEM SHALL add a scheduled workflow `.github/workflows/eval-nightly.yml`
running Tier B on a cron, gated behind repository secrets, posting the report as a
job summary and opening/updating a tracking issue when the gate fails.

12.7 WHEN required secrets are absent, the nightly workflow SHALL skip cleanly with a
neutral result rather than fail red.

12.8 THE SYSTEM SHALL write a concise PR comment / job summary containing the
scorecard diff versus baseline — regressions first, then improvements, then unchanged.

---

### R13 — Reporting

**User story:** As an eval engineer and as a candidate explaining this work, I want
one artifact per run that tells the whole story, so that results are shareable
without a walkthrough.

**Acceptance criteria**

13.1 Every suite run SHALL emit `evals/results/<run_id>/report.json` (machine) and
`report.md` (human) plus `report.html` (self-contained, no external assets).

13.2 The human report SHALL contain, in order: headline verdict; scorecard table
(backend × scenario × outcome); regressions vs. baseline; failure-mode incidence with
raw and bias-corrected rates and `n`; **reliability-budget-by-layer** — failure
incidence grouped by taxonomy `layer` (model / framework / harness / provider); judge
alignment summary with TPR/TNR/κ and eligibility; guardrail precision-recall table;
cost and latency; flaky cells; and full provenance.

13.3 Every rate in every report SHALL be printed as `value (n=N, 95% CI [lo, hi])`.

13.4 The report SHALL name, for each failed check, the `trace_id` and `span_id` that
produced the failure, so any number can be traced back to evidence in one hop.

13.5 THE SYSTEM SHALL keep the existing `format_scorecard()` output available as a
terminal view.

13.6 THE SYSTEM SHALL emit `evals/results/<run_id>/summary.txt` of ≤ 20 lines
suitable for a commit message or Slack paste.

---

### R14 — Reproducibility and provenance

**User story:** As an eval engineer, I want every number to carry enough metadata to
reproduce it, so that a result from three months ago is still interpretable.

**Acceptance criteria**

14.1 Every trace, verdict, and report SHALL record: `git_sha`, `git_dirty` (bool),
`taxonomy_version`, `prompt_hash` (per judge), `model_ids` (per role and per judge),
`pricing_table_version`, `python_version`, `platform`, `seed`, `tier`, and
`harness_version`.

14.2 WHEN the working tree is dirty, THE SYSTEM SHALL still run but SHALL stamp
`git_dirty: true` and SHALL refuse `baseline accept`.

14.3 THE SYSTEM SHALL version the trace schema and SHALL provide a migration path:
loading a trace with an older `schema_version` SHALL either upgrade it in memory or
fail with a named migration to run — never silently misinterpret fields.

14.4 THE SYSTEM SHALL record the exact scenario JSON content hash on each trace, so a
scenario edit is visible as a break in comparability rather than a mysterious
metric shift.

---

### R15 — Documentation and defensibility

**User story:** As a candidate discussing this system in an interview, I want the
repo to explain the methodology and its limits, so that the work reads as considered
rather than assembled.

**Acceptance criteria**

15.1 THE SYSTEM SHALL rewrite `docs/EVALS.md` to describe what is *implemented*,
moving aspirational content to `docs/EVALS_ROADMAP.md`. The current file's own scope
note admits several documented paths do not exist; that gap SHALL be closed.

15.2 THE SYSTEM SHALL add `docs/EVAL_METHODOLOGY.md` covering: why error analysis
precedes metrics; why binary over Likert; how the golden set was built and split;
measured judge TPR/TNR with confidence intervals; the bias-correction formula and
when it is suppressed; and an explicit **Limitations** section.

15.3 The Limitations section SHALL state plainly: single annotator, sample sizes,
the vendor-overlap confound for the Claude Agent SDK backend, which judges are
advisory rather than gating, and which failure modes remain `manual` detection.

15.4 `docs/posts/failure-taxonomy.md` SHALL be cross-linked to
`evals/taxonomy/failure_modes.yaml` so the essay and the machine-readable taxonomy
reference each other by FM ID.

15.5 THE SYSTEM SHALL add `evals/README.md` with a five-minute quickstart: build the
corpus from existing workspaces, run Tier A, read the report.

---

### R16 — Harness self-test

**User story:** As a maintainer, I want the eval harness itself covered by automated
tests at the levels defined in design §7, so that a broken check, flaky sampler, or
non-deterministic Tier A cannot silently ship.

**Acceptance criteria**

16.1 THE SYSTEM SHALL maintain unit tests under `tests/unit/evals/` covering at
minimum: taxonomy loader (valid + each invalid variant); every registered check with
fail / pass / `not_applicable` fixtures; check mutation sensitivity; check purity
(network blocked) and performance (< 5 s over 200 traces); alignment math; reliability
math (including Wilson CI published values and `pass^k` at k ∈ {1,3,5}); cost source
paths and budget abort; golden `assign_split` determinism and ~40/60 distribution over
≥ 10 000 synthetic ids; binary-judge grounding (`ungrounded` → `error`), three-attempt
error contract (never coerce to `fail`), prompt version validation, and cache hits with
sockets blocked; `--allow-retest` / validation-log guard; `baseline accept` refuses
when `git_dirty`.

16.2 THE SYSTEM SHALL maintain integration tests under `tests/integration/evals/`
covering: `TraceBuilder.from_workspace()` against `tests/fixtures/mini_workspace/`;
full Tier A pipeline determinism (two runs, `report.json` equal modulo `generated_at`);
gate rows from R12.2 via synthetic report/baseline pairs (may share fixtures with unit);
Tier A under a `socket` monkeypatch that raises on connect.

16.3 THE SYSTEM SHALL NOT assert judge quality in `tests/` (no
`assert judge_score >= …` / `assert verdict == "pass"` against a live model). Judge
quality is measured via the golden set (R8), not pytest.

16.4 `uv run pytest tests/unit/evals tests/integration/evals -q` SHALL pass with no
network and no API keys required.

---

## Traceability

| Requirement | Primary artifacts |
| --- | --- |
| R1, R2 | `evals/trace/`, `evals/store.py`, `evals/traces/` |
| R3 | `evals/annotate.py`, `evals/annotations/` |
| R4 | `evals/taxonomy/failure_modes.yaml`, `evals/taxonomy/loader.py` |
| R5 | `evals/checks/` |
| R6 | `evals/corpora/guardrails/`, `evals/guardrail_eval.py`, reuses `src/ai_team/guardrails/corpus_metrics.py` |
| R7 | `evals/judges/`, refactor of `evals/fixtures/` |
| R8 | `evals/alignment.py`, `evals/golden/` |
| R9 | `evals/reliability.py` |
| R10 | `evals/cost.py`, `evals/pricing.yaml` |
| R11 | `evals/fixtures/traces/`, `evals/judges/cache/` |
| R12 | `evals/baselines/`, `.github/workflows/ci.yml`, `.github/workflows/eval-nightly.yml` |
| R13 | `evals/report.py`, `evals/results/` |
| R14 | `evals/provenance.py` |
| R15 | `docs/EVALS.md`, `docs/EVAL_METHODOLOGY.md`, `evals/README.md` |
| R16 | `tests/unit/evals/`, `tests/integration/evals/` |
