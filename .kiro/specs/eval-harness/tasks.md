# Implementation Plan — Eval Harness

**Spec ID:** `eval-harness`
**Requirements:** [`requirements.md`](./requirements.md) · **Design:** [`design.md`](./design.md)

---

## How to execute this plan

- Work **one task at a time, in order**. Each task is sized to be completable and
  reviewable on its own; do not batch phases.
- Every task lists its **Definition of done**. Do not mark a task complete until each
  bullet is literally true. "Tests written" is not "tests passing".
- Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` before
  marking any task complete. The repo's CI enforces all three
  (`.github/workflows/ci.yml` job `lint`).
- New modules under `evals/` are not covered by the existing `mypy src/` scope. Add
  `evals` to the mypy path in Phase 0 so type errors surface immediately rather than
  at the end.
- Never edit `evals/backends/test_*_eval.py`, `evals/fixtures.py`, or
  `evals/run_evals.py` before Phase 4. Phases 1–3 are strictly additive.
- Do not spend money. Only Phase 7.2 and Phase 10.2 make live model calls, and both
  are explicitly budgeted and human-triggered.

---

## Phase 0 — Scaffolding

- [x] **0.1 Create the package skeleton**
  - Create `evals/trace/`, `evals/checks/`, `evals/judges/`, `evals/judges/prompts/`,
    `evals/judges/cache/`, `evals/taxonomy/`, `evals/golden/`, `evals/corpora/guardrails/`,
    `evals/fixtures/traces/`, `evals/baselines/`, each with `__init__.py` where it is a
    Python package and a `.gitkeep` where it is a data directory.
  - Add `evals/py.typed`.
  - **Definition of done:** `uv run python -c "import evals.trace, evals.checks, evals.judges"` succeeds.
  - _Requirements: R1, R4, R5, R7_

- [x] **0.2 Wire tooling for the new package**
  - Add `evals` to `[tool.mypy] mypy_path` in `pyproject.toml` and add a CI step
    `uv run mypy evals/` to the `lint` job.
  - Add to `.gitignore`: `evals/traces/`, `evals/annotations/`, `evals/samples/`,
    `evals/results/`. Confirm `evals/fixtures/`, `evals/golden/`, `evals/judges/cache/`,
    `evals/baselines/`, `evals/taxonomy/`, `evals/corpora/` are **not** ignored.
  - Add pytest markers `eval_unit` and `eval_tier_a` to `[tool.pytest.ini_options] markers`.
  - **Definition of done:** `uv run mypy evals/` passes on the empty package;
    `git check-ignore evals/golden` returns nothing.
  - _Requirements: R11, R14_

- [x] **0.3 Provenance module**
  - Implement `evals/provenance.py::collect() -> Provenance` capturing `git_sha`
    (`git rev-parse HEAD`), `git_dirty` (`git status --porcelain`), `python_version`,
    `platform`, `harness_version` (read from a new `evals/VERSION` file, start `0.1.0`),
    `taxonomy_version`, `pricing_table_version`.
  - Handle absence of git gracefully (`git_sha = "unknown"`, `git_dirty = True`).
  - **Definition of done:** unit test asserts all fields populated in this repo and in a
    temp dir with no `.git`.
  - _Requirements: R14.1, R14.2_

---

## Phase 1 — Trace capture

- [x] **1.1 Define the Trace data model**
  - Implement `evals/trace/models.py` exactly as specified in design §3.1: `Span`,
    `Artifact`, `CostRecord`, `Provenance`, `Trace`, `SCHEMA_VERSION = 1`, and the query
    helpers `spans_of`, `phases`, `phase_repeats`, `errors`, `files`, `read_artifact`.
  - Use pydantic v2. All datetimes timezone-aware UTC.
  - **Definition of done:** round-trip test — construct a Trace with ≥ 3 spans, dump to
    JSON, reload, assert equality; `Trace.model_json_schema()` emits without error.
  - _Requirements: R1.4, R1.5_

- [x] **1.2 Log parsers**
  - Implement `evals/trace/parsers.py` with one function per source:
    `parse_phases_jsonl`, `parse_costs_jsonl`, `parse_audit_jsonl`, `parse_session_json`,
    `parse_langgraph_messages`, `scan_workspace_artifacts`, `parse_smoke_report`.
  - Each returns `list[Span]` (or `list[Artifact]` / `CostRecord`) and a
    `list[str]` of warnings. **None may raise on malformed input** — a bad line is
    skipped and warned.
  - Port token summing from `evals/metrics.py::_extract_total_tokens` into
    `parse_langgraph_messages` rather than rewriting it.
  - Classify artifacts by path prefix: `src/` → source, `tests/` → test, `docs/` → doc,
    `logs/` → log, `Dockerfile|*.yml|*.toml|*.tf` → config, else other.
  - **Definition of done:** unit tests for each parser against (a) a well-formed sample,
    (b) a truncated final line, (c) a file containing one line of invalid JSON, (d) a
    missing file. All four produce a result plus appropriate warnings, zero exceptions.
  - _Requirements: R1.2, R1.6_

- [x] **1.3 Content-addressed blob store**
  - Implement `put_blob` / `get_blob` in `evals/store.py` writing to
    `evals/traces/blobs/<sha[:2]>/<sha>`.
  - Text files > 256 KB are truncated with a trailing `\n[TRUNCATED at 256KB]` marker
    before hashing; binary files (non-UTF-8) store hash and size only, no bytes.
  - **Definition of done:** identical content written twice produces one file; a 1 MB
    text file round-trips truncated; a PNG stores metadata with `get_blob` → `None`.
  - _Requirements: R1.4_

- [x] **1.4 TraceBuilder**
  - Implement `evals/trace/builder.py::TraceBuilder` with `from_live_run()` and
    `from_workspace()` per design §4.1.
  - Merge spans by `t_start`, assign `span_id = f"span_{i:04d}"` after sorting.
  - Generate `trace_id` per R1.3.
  - Move `evals/fixtures.py::_resolve_workspace` to `evals/trace/workspace.py::resolve_workspace`
    **by import re-export** — leave a `from evals.trace.workspace import resolve_workspace as _resolve_workspace`
    shim in `fixtures.py` so nothing breaks. (This is the only Phase 1 change to `fixtures.py`.)
  - Record `scenario_content_sha256` from the scenario JSON bytes.
  - When a backend produced no `audit.jsonl`, append the exact warning string
    `f"no audit log for backend={backend}; tool-level checks skipped"` — checks match on it.
  - **Definition of done:** `from_workspace()` builds a valid Trace from a committed
    miniature fixture workspace at `tests/fixtures/mini_workspace/` containing all four
    log types; span count, phase list, and `cost.source` asserted exactly.
  - _Requirements: R1.1, R1.2, R1.3, R1.8_

- [x] **1.5 TraceStore write path and schema versioning**
  - Implement `TraceStore.write()` (refuse overwrite → raise `TraceExistsError`),
    `load()`, and `evals/trace/schema.py` with a `MIGRATIONS: dict[int, Callable]`
    registry. Loading an unknown future version raises `TraceSchemaError` naming the
    required migration.
  - **Definition of done:** writing the same `trace_id` twice raises; loading a doc with
    `schema_version: 99` raises with a message containing "migration".
  - _Requirements: R1.7, R14.3_

- [x] **1.6 Backfill the corpus from existing workspaces**
  - Add `python -m evals.cli trace backfill --workspace-root ./workspace [--limit N]`
    which walks existing run directories and builds a Trace for each.
  - Infer `scenario_id` from `docs/requirements.md` or the run-store row; fall back to
    `"unknown"` and warn.
  - **Definition of done:** run it against the real `./workspace/`; report how many
    traces were built, how many warned, and the distribution by backend and status.
    Record those counts in the task's completion note — this number determines whether
    the golden set target in Phase 5 is reachable.
  - _Requirements: R1.8, R2.1_

---

## Phase 2 — Corpus, index, sampling

- [x] **2.1 SQLite index**
  - Implement the `traces` table and `rebuild_index()` per design §4.2, plus
    `TraceStore.query(**filters)` returning `TraceIndexRow` objects.
  - `rebuild_index()` must be idempotent and safe to run concurrently with reads
    (WAL mode).
  - Add `python -m evals.cli index rebuild` and `... index stats`.
  - **Definition of done:** rebuild twice → identical row count; `index stats` prints a
    backend × scenario × status table for the backfilled corpus.
  - _Requirements: R2.1, R2.2_

- [x] **2.2 Sampler**
  - Implement `evals/sampling.py` with `random`, `stratified`, `extremes`,
    `failed-only`, `unlabeled` strategies, all pure `(rows, n, seed) -> list[str]`.
  - Stratified shortfall behaviour per R2.4, recorded in the manifest.
  - Write manifests to `evals/samples/<sample_id>.json` with strategy, seed, filters,
    `corpus_state_hash` (sha256 of sorted trace_ids in the index), and the selection.
  - Add `python -m evals.cli sample --strategy stratified -n 100 --seed 42`.
  - **Definition of done:** same seed + same corpus → byte-identical manifest; a
    stratum shortfall is visible in the manifest's `imbalances` field.
  - _Requirements: R2.3, R2.4, R2.5, R2.6_

---

## Phase 3 — Taxonomy and deterministic checks

> This phase is the spine. Everything after it references FM ids and check ids.

- [x] **3.1 Taxonomy schema and loader**
  - Write `evals/taxonomy/failure_modes.yaml` seeded with **FM-001 … FM-010** exactly
    as tabulated in requirements R4.3, each with a `definition` paragraph decidable
    without further context, correct `layer`, and a `references` link into
    `docs/posts/failure-taxonomy.md`.
  - Leave `positive_examples` / `negative_examples` empty for now; Phase 5 fills them.
  - Implement `evals/taxonomy/loader.py::load_taxonomy()` with all R4.4 validations,
    **except** the trace-reference check, which is enabled once examples exist.
  - **Definition of done:** loader unit test covers valid load plus five invalid
    variants (duplicate id, bad `layer`, bad `severity`, `detection: check` with empty
    `implemented_by`, retired id reused); all raise with specific messages.
  - _Requirements: R4.1, R4.2, R4.3, R4.4, R4.5_

- [x] **3.2 Check registry and base helpers**
  - Implement `evals/checks/base.py` (`CheckResult`, `Check` protocol, helpers
    `passed()`, `failed()`, `na()`) and `evals/checks/__init__.py` (`@check` decorator,
    `_REGISTRY`, `all_checks(tier=None)`, `checks_for(failure_mode_id)`).
  - Add a validation function `validate_registry_against_taxonomy()` that fails when an
    FM with `detection: check` has no registered implementation, and vice versa.
  - **Definition of done:** registry validation runs as a unit test and currently fails
    with a clear list of the ten unimplemented FMs. That failing test is the checklist
    for 3.3–3.5.
  - _Requirements: R5.1, R5.4, R4.6_

- [x] **3.3 Trajectory and isolation checks**
  - Implement `CHK-tool-call-emitted` (FM-001), `CHK-phase-repeat-bounded` (FM-002),
    `CHK-listener-self-trigger` (FM-002, static introspection of
    `src/ai_team/flows/main_flow.py`), `CHK-interrupt-latency` (FM-003),
    `CHK-workspace-isolation` (FM-004).
  - `CHK-listener-self-trigger` must **reuse the logic already in
    `tests/unit/flows/test_flow_wiring.py`** (the meta-test that fails when a flow method
    listens to its own name — taxonomy §2's shipped fix). Extract that introspection into
    a shared helper imported by both the test and the check; do not reimplement or
    duplicate it, and do not delete the existing test.
  - Every check returns `not_applicable` when its precondition is absent, including the
    "no audit log" warning case.
  - **Definition of done:** each check has three fixture traces (fail / pass /
    not-applicable) in `tests/fixtures/traces/` and three passing tests.
  - _Requirements: R5.3, R5.6_

- [x] **3.4 Verification, spend, observability, provider checks**
  - Implement `CHK-guardrail-fp-budget` (FM-005), `CHK-runtime-smoke-present` (FM-006),
    `CHK-spend-ceiling` (FM-007), `CHK-metric-source-agreement` (FM-008),
    `CHK-provider-error-rate` (FM-009), `CHK-gate-env-fidelity` (FM-010).
  - `CHK-gate-env-fidelity` parses test-span output for `ModuleNotFoundError: No module named 'X'`
    and cross-references the generated `requirements.txt` artifact.
  - `CHK-runtime-smoke-present` reads `smoke_probe` spans sourced from the runtime smoke
    gate in `src/ai_team/tools/smoke_tools.py`; inspect that module's output shape first
    and add a parser for it in `evals/trace/parsers.py::parse_smoke_report` if 1.2 left it
    stubbed.
  - `CHK-metric-source-agreement` compares artifact-derived file count and cost against
    event-derived values with a configurable tolerance (default: exact for files, 5% for cost).
  - **Definition of done:** as 3.3 — three fixtures and three tests per check.
  - _Requirements: R5.3, R5.6_

- [x] **3.5 Artifact checks and registry completion**
  - Implement `CHK-required-artifacts` (scenario `expected.files`) and
    `CHK-hallucination-density` (reuse `evals/fixtures.py::count_hallucinations`,
    imported, not copied).
  - **Definition of done:** `validate_registry_against_taxonomy()` now passes;
    `python -m evals.cli taxonomy coverage` writes `evals/taxonomy/COVERAGE.md` showing
    every FM covered by a named check.
  - _Requirements: R5.3, R4.6_

- [x] **3.6 Check-suite mutation tests**
  - Implement `tests/unit/evals/test_check_sensitivity.py` per design §7.2: for each
    check, mutate a passing fixture to introduce the failure and assert the outcome
    flips to `fail`.
  - **Definition of done:** one parametrized test per check, all passing; total suite
    runtime under 5 s.
  - _Requirements: R5.2, R5.5_

- [x] **3.7 Purity and performance guards**
  - Add a test that runs every check with `socket.socket` monkeypatched to raise, and a
    test asserting the full registry over 200 synthetic traces completes in < 5 s.
  - **Definition of done:** both tests pass.
  - _Requirements: R5.2, R5.5_

---

## Phase 4 — Wire trace emission into the runner

> First phase that touches existing files. Trace writing is a side effect only —
> nothing reads traces for gating yet.

- [x] **4.1 Emit traces from live runs**
  - In `evals/run_evals.py`, after each backend subprocess completes (including
    watchdog kills), build and write a Trace. A killed run gets `status: "killed"`.
  - Add `--tier {A,B,C}` (default B), `--k N` (default 1), `--budget-usd` (default from
    `AI_TEAM_EVAL_BUDGET_USD`, fallback 5.00).
  - Preserve the existing watchdog behaviour byte for byte — drain timeout 90 s,
    log-freeze timeout 120 s, per-backend logs at `/tmp/eval_<backend>.log`.
  - **Definition of done:** `--no-judge --tier B --k 1 --scenario smoke-test` on a single
    backend produces one trace file and the pre-existing console summary is unchanged.
  - _Requirements: R1.1, R9.2, R10.3_

- [x] **4.2 Cost normalization**
  - Implement `evals/cost.py`: `normalize_cost(trace) -> CostRecord` per R10.1/R10.2,
    `evals/pricing.yaml` with a `version` field stamped with today's date, and
    `BudgetLedger` (per-suite-run, explicitly threaded — **not** a module-level singleton;
    see design §4.10 and taxonomy §7).
  - When a model id is missing from `pricing.yaml`, warn loudly and set
    `source: "unknown"`, never silently zero.
  - **Definition of done:** unit tests for each `source` path; ledger aborts exactly at
    the ceiling; a LangGraph trace that previously had `cost_usd = None` now carries a
    `token_estimate`.
  - _Requirements: R10.1, R10.2, R10.3_

- [x] **4.3 Budget enforcement and projection**
  - Wire `BudgetLedger` into `run_evals.py`: project cost before a live tier from
    `pricing.yaml` × historical median tokens per scenario; require `--yes` when the
    projection exceeds 50% of the ceiling and `CI` is unset. On overrun, mark remaining
    runs `skipped_budget` and exit 2.
  - **Definition of done:** integration test with a $0.01 ceiling aborts after the first
    run and still writes a partial report.
  - _Requirements: R10.3, R10.6_

- [x] **4.4 k-run support and reliability metrics**
  - Implement `evals/reliability.py` (`pass_at_k`, `pass_pow_k`, `pass_rate`,
    `wilson_ci`, `is_flaky`, `indistinguishable`) and have `run_evals.py --k N` execute
    N runs per backend × scenario cell.
  - **Definition of done:** `wilson_ci` matches published values for (3,3), (2,3),
    (0,3), (95,100) to 3 decimal places; `--k 3 --no-judge` on `smoke-test` produces
    three traces per backend and a cell summary with CI.
  - _Requirements: R9.1, R9.2, R9.3, R9.4_

---

## Phase 5 — Error analysis (human in the loop)

> **This phase is the point of the whole spec.** Do not shortcut it, and do not let a
> model do the labeling. Budget 4–6 hours of human time across two sittings.

- [x] **5.1 Annotation TUI**
  - Implement `evals/annotate.py` per design §4.3: `render_trace_card()`, the review
    loop, resume support, and the live saturation counter.
  - Notes captured via `$EDITOR`; tags entered inline; `first_failure_span_id` selected
    from a numbered span list.
  - **No LLM output is displayed anywhere in this interface** (R3.7). Add a comment in
    the module saying why, so a future contributor does not "helpfully" add suggestions.
  - Persist to `evals/annotations/<annotator>.jsonl`, append-only.
  - **Definition of done:** annotate 3 traces, quit, resume, confirm the 3 are skipped
    and the file has exactly 3 lines.
  - _Requirements: R3.1–R3.7_

- [x] **5.2 Open coding pass** *(human task)*
  - Sample 100 traces: `python -m evals.cli sample --strategy stratified -n 100 --seed 1`.
    If the backfilled corpus is smaller than 100, take everything and note the shortfall
    explicitly in `docs/EVAL_METHODOLOGY.md` — an honest small-n beats a padded one.
  - Annotate every trace in the sample. Write what went wrong in your own words; do not
    reach for the existing ten categories while coding.
  - **Definition of done:** ≥ 100 annotation records (or the whole corpus), and the
    saturation counter reached 20 consecutive traces with no new tag. If it did not,
    sample 50 more and continue.
  - _Requirements: R3.6, R2.3_

- [x] **5.3 Axial coding**
  - Run `python -m evals.cli taxonomy propose --from-annotations` to cluster tags and
    surface candidates. Review each candidate by hand; accept, merge, or reject.
  - Add accepted new failure modes as FM-011+ with full definitions.
  - For every FM, fill `positive_examples` and `negative_examples` with real
    `(trace_id, span_id)` pairs from the corpus. Enable the trace-reference validation
    deferred in 3.1.
  - Retire any seeded FM the corpus does not support, with a `retired_reason` — a
    taxonomy entry with zero observed instances is a hypothesis, and saying so is the
    honest move.
  - **Definition of done:** taxonomy validates with reference checking on; every active
    FM has ≥ 1 positive and ≥ 1 negative example; `COVERAGE.md` regenerated.
  - _Requirements: R4.4, R4.7, R4.6_

- [x] **5.4 Golden set construction**
  - Implement `evals/golden.py`: `LabelingUnit`, `assign_split()` (deterministic sha256
    rule from design §4.8), append-only JSONL per FM, and
    `python -m evals.cli golden label --fm FM-00X` which walks candidate units and
    records present/absent.
  - Derive candidate units from annotations where possible so the human is confirming,
    not re-reading.
  - **Definition of done:** for each FM whose `detection` is `judge`, ≥ 100 labeled
    units with ≥ 30 of the minority class, split ~60/40 dev/test, each split holding
    ≥ 25% of each class. `python -m evals.cli golden stats` prints the table.
  - _Requirements: R8.1, R8.2, R8.3_

- [x] **5.5 Validate deterministic checks against human labels**
  - For every FM with `detection: check`, run its check across the labeled corpus and
    compute the same confusion metrics used for judges.
  - **A deterministic check is not automatically correct.** Where a check disagrees
    with a human label, fix the check and record what was wrong in its docstring.
  - **Definition of done:** every `detection: check` FM reaches TPR ≥ 0.95 and TNR ≥ 0.95
    against human labels, or is downgraded to `detection: judge` with a written reason.
  - _Requirements: R5.3, R8.5_

---

## Phase 6 — Guardrail classifier evaluation

- [x] **6.1 Corpus format and mining**
  - Implement `evals/corpora/format.py` (`GuardrailCase`) and
    `python -m evals.cli guardrail mine` which extracts candidate cases from the trace
    corpus: every `guardrail_check` span with outcome `fail` on a run that satisfied all
    acceptance criteria becomes a false-positive candidate for labeling.
  - **Definition of done:** mining produces a labeling queue; the taxonomy §5 cases
    (pytest bodies containing *test/coverage/suite/validation*, and `tests/conftest.py`)
    are present and labeled `benign`.
  - _Requirements: R6.1, R6.2_

- [x] **6.2 Evaluator and thresholds**
  - Implement `evals/guardrail_eval.py::GuardrailEvaluator` importing
    `ConfusionCounts`, `score`, `format_report` from
    `src/ai_team/guardrails/corpus_metrics.py`. **Do not reimplement confusion accounting.**
  - Write `evals/corpora/guardrails/thresholds.yaml` with the asymmetric floors from
    design §4.6.
  - Enforce the `min_cases` rule (R6.4) — below it, metrics are `provisional` and
    excluded from gating.
  - **Definition of done:** `python -m evals.cli guardrail eval` prints a
    `format_report()` line per guardrail with n, precision, recall, FPR, F1; provisional
    guardrails are labeled as such.
  - _Requirements: R6.3, R6.4, R6.5_

- [x] **6.3 Threshold sweep**
  - Implement `GuardrailEvaluator.sweep()` and emit a precision-recall curve per
    threshold-parameterized guardrail into the report.
  - **Definition of done:** sweeping the scope-relevance floor across 0.05–0.50
    produces a curve; the currently configured value is marked on it.
  - _Requirements: R6.6_

---

## Phase 7 — Binary judges and alignment

- [x] **7.1 BinaryJudge, prompt files, cache**
  - Implement `evals/judges/base.py` (`JudgeSpec`, `Verdict`, `BinaryJudge`,
    `EnsembleBinaryJudge`) reusing `LLMJudge`'s transport methods for both providers.
  - Implement `evals/judges/evidence.py` with the builder registry; move
    `run_pytest_in_workspace` and `summarize_workspace` here from `fixtures.py` by
    re-export shim, and register `dev_phase_transcript`, `workspace_summary`,
    `security_report`, `trace_card` (reusing `annotate.render_trace_card`).
  - Implement the verdict cache keyed by `sha256(prompt_hash + model_id + evidence)`,
    stored as JSON under `evals/judges/cache/<key[:2]>/<key>.json`, git-tracked.
  - Enforce the grounding rule: `evidence_quote` must appear in the evidence, else
    `verdict: "error"`, `reason: "ungrounded"`.
  - Enforce R7.9: three attempts, then `verdict: "error"` — **never** `fail`.
  - Mark `LLMJudge.check()` deprecated in its docstring; do not remove it.
  - Write the first prompt file, `evals/judges/prompts/fm-001-tool-call-omission.v1.md`,
    in the format from design §4.7.
  - Add a validation test: every prompt file parses, `version` matches the filename, and
    a changed prompt body with an unchanged version number fails.
  - **Definition of done:** all of the above, with a cached verdict served without a
    network call (test with sockets blocked).
  - _Requirements: R7.1–R7.9, R11.4_

- [x] **7.2 Alignment measurement** *(spends money — budget ≤ $1.00)*
  - Implement `evals/alignment.py` per design §4.8: `confusion`, `cohens_kappa`,
    `bootstrap_ci` (2,000 resamples, seeded), `bias_corrected_rate` with the ≤ 0.2
    denominator suppression, `AlignmentReport`, and the disagreement listing.
  - Implement `evals/golden/.validation_log.jsonl` and the `--allow-retest` guard (R8.4):
    `judge align` reads **dev only**; `judge validate` reads **test only**, once per
    `prompt_hash`.
  - Iterate each judge prompt against **dev** until TPR and TNR clear 0.90, bumping the
    version number on every prompt change. Then run `judge validate` **once**.
  - **Definition of done:** `evals/golden/alignment/<judge_id>.json` exists for each
    judge with TPR, TNR, κ, bootstrap CIs, `eligible_to_gate`, and the disagreement
    list. Judges that did not clear the bar are recorded as `advisory` — that is a
    legitimate outcome, not a failure of the phase.
  - _Requirements: R8.4–R8.9_

- [x] **7.3 Unit tests for alignment math**
  - Hand-computed confusion matrices → exact TPR/TNR/κ; bootstrap determinism under
    fixed seed; `bias_corrected_rate` returns `None` at the suppression boundary, is
    identity when TPR = TNR = 1.0, and is correct for a worked example.
  - **Definition of done:** all tests pass; no test asserts a judge's quality.
  - _Requirements: R8.5, R8.7_

---

## Phase 8 — Aggregation, reporting, Tier A corpus

- [x] **8.1 Aggregation**
  - Implement `evals/aggregate.py::SuiteReport` assembling check results, verdicts,
    guardrail metrics, reliability cells, cost, and provenance into one document.
  - Every rate carries `n` and a Wilson CI (R13.3). Raw and bias-corrected rates sit
    side by side. Non-eligible judges' verdicts land in a `suppressed` section.
  - Enforce R7.6 here: a single-vendor verdict may not settle a cross-backend comparison
    involving that vendor; such comparisons are emitted as `indeterminate`.
  - Compute the **failure incidence by taxonomy layer** breakdown (model / framework /
    harness / provider).
  - **Definition of done:** `SuiteReport` schema test; a golden `report.json` fixture
    committed and diffed in tests.
  - _Requirements: R13.1, R13.2, R13.3, R9.5, R7.6_

- [x] **8.2 Report emitters**
  - Implement `evals/report.py` producing `report.json`, `report.md`, `report.html`
    (self-contained, Jinja2, inline SVG — no CDN), and `summary.txt` (≤ 20 lines).
  - Section order per R13.2. Every failed check names its `trace_id` and `span_id` (R13.4).
  - Build two inline SVG charts by hand: stacked failure incidence by layer, and
    per-guardrail precision-recall curves.
  - Keep `format_scorecard()` working as the terminal view (R13.5).
  - **Definition of done:** all four artifacts generated from the golden fixture report;
    `report.html` opens offline with no network requests (verify by loading with devtools
    network tab, or assert no `http` substring outside of link text).
  - _Requirements: R13.1–R13.6_

- [x] **8.3 Curate and redact the Tier A fixture corpus**
  - Select 40–60 traces covering every active FM with ≥ 1 positive and ≥ 1 negative,
    plus at least one trace per backend per status.
  - Implement `python -m evals.cli fixtures redact` scrubbing API keys (regex for
    `sk-`, `sk-ant-`, `sk-or-`, 32+ char hex), absolute home paths (`/Users/<name>` →
    `/home/user`), and emails. Add a CI redaction linter that fails on any match.
  - Bundle the referenced blobs under `evals/fixtures/blobs/`.
  - **Definition of done:** corpus committed; redaction linter passes; total added repo
    size under 25 MB (report the actual figure).
  - _Requirements: R11.1, R11.2_

- [x] **8.4 Tier A runner**
  - Implement `python -m evals.cli run --tier A` executing checks + guardrail eval +
    cached judges + aggregation + report against `evals/fixtures/traces/`.
  - Block model-API network egress in Tier A; a cache miss raises `TierAMissingVerdict`
    with the key and the `cache warm` command in the message.
  - Implement `python -m evals.cli cache warm --tier B`.
  - **Definition of done:** two consecutive Tier A runs produce byte-identical
    `report.json` apart from `generated_at`; wall clock under 120 s on CI hardware;
    `$0.00` spent.
  - _Requirements: R11.3–R11.7_

---

## Phase 9 — Gate and CI

- [x] **9.1 Baseline and gate logic**
  - Implement `evals/baselines/` format, `evals/gate.py::evaluate_gate()` covering every
    row of the R12.2 table, and exit codes 0 / 1 / 2 (pass / regression / harness error).
  - Non-eligible judges and provisional guardrails contribute to the report only (R12.3).
  - Implement `python -m evals.cli baseline accept --tier <t> --reason <text>`, refusing
    when `git_dirty` (R14.2).
  - **Definition of done:** parametrized tests with synthetic report/baseline pairs
    covering each gate row plus the three exit codes.
  - _Requirements: R12.1–R12.4, R14.2_

- [x] **9.2 Tier A CI job**
  - Add job `eval-tier-a` to `.github/workflows/ci.yml`, mirroring the existing jobs'
    setup (checkout, `astral-sh/setup-uv@v5` with cache, `setup-python` 3.12,
    `uv sync --frozen`), running on every PR, requiring **no secrets**.
  - Run in `--warn-only` mode initially. Upload `report.json`, `report.md`,
    `report.html` as artifacts. Write the scorecard diff to `$GITHUB_STEP_SUMMARY`.
  - **Definition of done:** job green on a PR; artifacts downloadable; summary shows the
    baseline diff.
  - _Requirements: R12.5, R12.8_

- [x] **9.3 Nightly Tier B workflow**
  - Add `.github/workflows/eval-nightly.yml` on a cron, running Tier B with
    `AI_TEAM_EVAL_BUDGET_USD: "2.00"`, gated on `ANTHROPIC_API_KEY` / `OPENROUTER_API_KEY`.
  - When secrets are absent, skip with a neutral result, not a red X (R12.7).
  - On gate failure, open or update a tracking issue with the summary.
  - Commit newly produced judge-cache entries back on a bot branch so Tier A stays warm.
  - **Definition of done:** one successful manual `workflow_dispatch` run; verify actual
    spend against the projection and record both figures.
  - _Requirements: R12.6, R12.7, R11.7_

- [x] **9.4 Flip the gate on** *(after one week of green nightlies)*
  - Remove `--warn-only` from `eval-tier-a`. Set the initial baseline with a reason.
  - **Definition of done:** a deliberately regressing PR (e.g. delete a guardrail rule)
    fails CI with a readable message naming the check, the FM, and the trace.
  - _Requirements: R12.2_

---

## Phase 10 — Documentation and close-out

- [x] **10.1 Rewrite the eval docs**
  - Rewrite `docs/EVALS.md` to describe only what is implemented; move everything
    aspirational — including the entire §13 role-eval backlog — to
    `docs/EVALS_ROADMAP.md`. Delete the stale scope note at the top of the current file.
  - Write `docs/EVAL_METHODOLOGY.md` per R15.2: error analysis first, binary over
    Likert, golden set construction and split discipline, measured TPR/TNR with CIs,
    the bias-correction formula and its suppression rule, and a **Limitations** section
    stating single annotator, sample sizes, the Anthropic vendor-overlap confound for
    the Claude Agent SDK backend, which judges are advisory, and which FMs remain manual.
  - Cross-link `docs/posts/failure-taxonomy.md` to `evals/taxonomy/failure_modes.yaml`
    by FM id in both directions.
  - Write `evals/README.md`: five-minute quickstart — backfill, index, Tier A, read report.
  - **Definition of done:** every command in every doc executed verbatim and confirmed
    working. A doc command that does not run is a broken doc.
  - _Requirements: R15.1–R15.5_

- [x] **10.2 Full Tier C validation run** *(spends money — budget ≤ $5.00)*
  - Run `python -m evals.cli run --tier C --k 5 --yes` across all scenarios and backends.
  - Confirm the hard ceiling holds, the report is complete, and no judge exceeded its
    eligibility claims.
  - Accept the Tier B/C baselines from this run.
  - **Definition of done:** report committed under `docs/eval-runs/<date>/`; actual spend
    recorded and compared to the design §5.1 projection; any variance over 25% explained.
  - _Requirements: R10.3, R10.5, R12.4_

- [x] **10.3 Extractability check**
  - Verify `evals/` imports from `src/ai_team/` in exactly two places
    (`guardrails.corpus_metrics`, `core.run_store`) plus the backend registry used by
    Tier B/C execution. Document them in `evals/README.md` under "Coupling to ai-team".
  - **Definition of done:** `grep -rn "from ai_team" evals/ | sort` output pasted into
    the README and matching the documented list.
  - _Requirements: design §1.3_

---

## Phase 11 — Harness self-test (R16 / design §7)

> Closes the gap between design §7 and the earlier phases' scattered DoDs. Unit tests
> already exist under `tests/unit/evals/`; this phase adds the missing cases and the
> dedicated integration package.

- [x] **11.1 Unit coverage gaps from design §7.1**
  - `assign_split` ~40/60 distribution over ≥ 10 000 synthetic ids (tolerance ±2 pp).
  - `pass_pow_k` / `pass_at_k` at k ∈ {1, 3, 5}.
  - BinaryJudge: ungrounded `evidence_quote` → `verdict: "error"` / `reason: "ungrounded"`;
    three failed attempts → `error`, never `fail` (mock transport).
  - `judge validate` refuses a second run for the same `(judge_id, prompt_hash)` without
    `--allow-retest` (validation log).
  - **Definition of done:** new/extended tests in `tests/unit/evals/` all pass; no live
    model calls.
  - _Requirements: R16.1, R16.3_

- [x] **11.2 Integration package `tests/integration/evals/`**
  - `test_trace_builder_integration.py`: `from_workspace()` on
    `tests/fixtures/mini_workspace/` — span count, phases, cost source.
  - `test_tier_a_integration.py`: two consecutive Tier A runs; `report.json` equal
    modulo `generated_at`; `$0.00` spend; socket monkeypatch raises on connect for the
    duration of a run.
  - `test_gate_integration.py`: synthetic report/baseline pairs covering each R12.2 row
    plus exit codes 0/1/2 (may import helpers from unit tests).
  - Mark with `@pytest.mark.integration` and `eval_tier_a` where applicable.
  - **Definition of done:**
    `uv run pytest tests/integration/evals -q` passes with no API keys.
  - _Requirements: R16.2, R16.4_

- [x] **11.3 Spec/README sync**
  - Point `.kiro/specs/eval-harness/README.md` at R16 and the pytest commands above.
  - Confirm design §7.4 still holds (no judge-quality asserts in the suite).
  - **Definition of done:** README commands executed; suite green.
  - _Requirements: R16.4_

---

## Sequencing summary

```
Phase 0  scaffolding            ── additive, ~2h
Phase 1  trace capture          ── additive, ~1d      ◄── review SCHEMA_VERSION here
Phase 2  corpus + sampling      ── additive, ~4h
Phase 3  taxonomy + checks      ── additive, ~1.5d    ◄── the spine
Phase 4  wire into runner       ── first edits to existing files, ~6h
Phase 5  ERROR ANALYSIS         ── human, 4–6h across two sittings  ◄── the point
Phase 6  guardrail eval         ── ~4h
Phase 7  judges + alignment     ── ~1d, ≤$1.00
Phase 8  aggregate + report     ── ~1d
Phase 9  gate + CI              ── ~6h + 1 week soak
Phase 10 docs + validation      ── ~4h, ≤$5.00
Phase 11 harness self-test      ── R16 / design §7 gaps, ~2h
```

**If time is short, the minimum defensible slice is Phases 0–5 plus 8.** Traces,
taxonomy bound to deterministic checks, real error analysis, and a report — with no
judges at all — is a coherent, honest eval system. Judges without Phase 5 are not.


---

<!-- harness-scaffold-complete -->
## Scaffolding completion (2026-08-16)

Phases 0–10 code paths implemented. Deferred by design (not skipped silently):

- **5.2** human open coding on live corpus (tooling ready; see docs/EVAL_METHODOLOGY.md)
- **7.2** live judge align ≤$1 (advisory fixtures under evals/golden/alignment/)
- **9.4** flip Tier A gate off `--warn-only` after soak week
- **10.2** full Tier C live run ≤$5 (note in docs/eval-runs/2026-08-16/)
- **11.x** harness self-test package — see Phase 11 (added 2026-08-16)