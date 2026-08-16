# Design — Eval Harness

**Spec ID:** `eval-harness`
**Requirements:** [`requirements.md`](./requirements.md)
**Tasks:** [`tasks.md`](./tasks.md)

---

## 1. Overview

### 1.1 The central architectural move

Today, execution and scoring are fused: `evals/backends/test_*_eval.py` runs a
backend inside a pytest fixture and asserts on the live result object. That fusion
is the root cause of three separate problems — evals cost money every time, they are
non-reproducible, and historical runs are unanalyzable.

**This design separates them.**

```
        EXPENSIVE, NON-DETERMINISTIC          CHEAP, DETERMINISTIC
        ─────────────────────────────         ─────────────────────
        backend.run(scenario)   ──────►  Trace  ──────►  Checks
                                          │              Judges (cached)
                                          │              Aggregation
                                          ▼              Reporting
                                    evals/traces/*.json  Gate
```

The **Trace** is the interface. Everything to the left of it is billed and flaky.
Everything to the right is free, fast, and repeatable. Every design decision below
follows from protecting that boundary.

This is also what makes the $5 constraint tractable: the corpus of past runs already
sitting in `./workspace/` becomes free training data for the harness, and a pull
request can be gated for $0.00.

### 1.2 Design principles

1. **Cheap detection first.** A failure mode gets a deterministic `Check` unless it
   provably cannot. Judges are the exception, not the default.
2. **Every number carries an `n` and a confidence interval.** The project's own
   history (guardrail floor moved on one batch's readings; three weeks blaming a
   framework for a wiring bug) is the argument for this.
3. **Ground truth is human and is never model-suggested.** Open coding shows no LLM
   output. The golden `test` split is touched once per prompt version.
4. **Prompts are code.** Files, versioned, hashed, diffable.
5. **Errors are not failures.** A judge that times out is `error`, excluded from
   denominators. The current `except: return passed=False` behaviour is a
   correctness bug this design fixes.
6. **Reuse what exists.** `corpus_metrics.py`, `EnsembleJudge`, `run_pytest_in_workspace`,
   the scenario JSON contracts, and the parallel-subprocess runner all survive.

### 1.3 What gets reused, refactored, and added

| Existing | Fate |
| --- | --- |
| `evals/fixtures.py::EvalResult` | Kept; becomes an input to `Trace.from_eval_result()` |
| `evals/fixtures.py::LLMJudge` | Kept, deprecated for gating; `BinaryJudge` built alongside, reusing its provider plumbing verbatim |
| `evals/fixtures.py::EnsembleJudge` | Kept and extended — `spread` / `contested` / `single_vendor` carry into `Verdict` |
| `evals/fixtures.py::run_pytest_in_workspace` | Moved to `evals/evidence.py`, unchanged behaviour |
| `evals/fixtures.py::count_hallucinations` | Becomes `CHK-hallucination-density` |
| `evals/fixtures.py::_resolve_workspace` | Becomes `evals/trace/workspace.py::resolve_workspace` |
| `evals/metrics.py::compute_metrics` | Split: measurement moves into checks; `format_scorecard` kept as a terminal view |
| `evals/run_evals.py` | Kept as the Tier B/C executor; gains `--tier`, `--k`, `--budget`, and trace emission. Watchdog logic unchanged. |
| `evals/scenarios/*.json` | Kept; schema extended additively (R14.4 content hash, `max_phase_repeats`, `k`) |
| `evals/backends/test_*_eval.py` | Kept; refactored to emit a Trace and assert via the check registry |
| `src/ai_team/guardrails/corpus_metrics.py` | Reused as-is by R6. Do not reimplement. |
| `src/ai_team/core/run_store.py` | Read-only source for retroactive trace construction |

---

## 2. Architecture

### 2.1 Layer diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│  L7  CLI / CI            python -m evals.cli  •  ci.yml  •  eval-nightly │
├──────────────────────────────────────────────────────────────────────────┤
│  L6  Gate & Report       baseline diff  →  exit code  •  json/md/html    │
├──────────────────────────────────────────────────────────────────────────┤
│  L5  Aggregation         rates + Wilson CI  •  pass^k  •  bias correction│
├──────────────────────────────────────────────────────────────────────────┤
│  L4  Scoring        ┌───────────────┬──────────────┬────────────────┐    │
│                     │ Checks (free) │ Judges(cache)│ Guardrail eval │    │
│                     └───────────────┴──────────────┴────────────────┘    │
├──────────────────────────────────────────────────────────────────────────┤
│  L3  Ground truth        Taxonomy YAML  •  Golden set  •  Alignment      │
├──────────────────────────────────────────────────────────────────────────┤
│  L2  Corpus              TraceStore (SQLite index)  •  Sampler  •  Annot │
├──────────────────────────────────────────────────────────────────────────┤
│  L1  Capture             TraceBuilder  ←  logs/*.jsonl, workspace, result│
├──────────────────────────────────────────────────────────────────────────┤
│  L0  Execution           run_evals.py  →  crewai | langgraph | sdk       │
└──────────────────────────────────────────────────────────────────────────┘
```

Tier A executes L1(read-only) → L6. Tier B/C executes L0 → L6.

### 2.2 File layout

```
evals/
├── __init__.py
├── cli.py                      # single Typer/argparse entry: python -m evals.cli
├── run_evals.py                # EXISTING — Tier B/C executor, extended
│
├── trace/
│   ├── __init__.py
│   ├── models.py               # Trace, Span, Artifact, CostRecord, Provenance
│   ├── builder.py              # TraceBuilder: logs + workspace + result → Trace
│   ├── workspace.py            # resolve_workspace (from fixtures._resolve_workspace)
│   ├── parsers.py              # phases.jsonl, costs.jsonl, audit.jsonl, session.json
│   └── schema.py               # SCHEMA_VERSION, migrations
│
├── store.py                    # TraceStore: write, load, index, query
├── sampling.py                 # Sampler strategies + sample manifests
├── annotate.py                 # open-coding TUI
│
├── taxonomy/
│   ├── failure_modes.yaml      # THE taxonomy
│   └── loader.py               # parse + validate + COVERAGE.md generation
│
├── checks/
│   ├── __init__.py             # registry + @check decorator
│   ├── base.py                 # Check protocol, CheckResult
│   ├── trajectory.py           # FM-001, FM-002, FM-003
│   ├── isolation.py            # FM-004
│   ├── guardrails.py           # FM-005
│   ├── verification.py         # FM-006, FM-010
│   ├── spend.py                # FM-007
│   ├── observability.py        # FM-008
│   ├── provider.py             # FM-009
│   └── artifacts.py            # required files, hallucination density
│
├── judges/
│   ├── __init__.py
│   ├── base.py                 # BinaryJudge, Verdict, JudgeSpec
│   ├── evidence.py             # evidence_builder registry (+ run_pytest_in_workspace)
│   ├── prompts/
│   │   ├── acceptance-criterion.v1.md
│   │   ├── fm-001-tool-call-omission.v1.md
│   │   └── ...
│   └── cache/                  # sha256-keyed verdict cache (git-tracked)
│
├── golden/
│   ├── FM-001.jsonl
│   └── ...
├── alignment.py                # TPR/TNR/κ, bootstrap CI, bias correction
├── reliability.py              # pass@k, pass^k, Wilson CI, flake detection
├── cost.py                     # cost normalization + budget enforcement
├── pricing.yaml                # $/Mtok per model id, versioned
├── aggregate.py                # SuiteScore assembly
├── report.py                   # json / md / html emitters
├── gate.py                     # baseline diff + exit code
├── provenance.py               # env, git, versions
│
├── corpora/guardrails/
│   ├── scope_relevance.jsonl
│   ├── role_boundary.jsonl
│   ├── security_patterns.jsonl
│   └── thresholds.yaml
│
├── fixtures/traces/            # committed, redacted Tier-A corpus (40–60 traces)
├── baselines/{tier_a,tier_b}.json
├── scenarios/                  # EXISTING
├── backends/                   # EXISTING test_*_eval.py, refactored
├── traces/                     # gitignored: live corpus + index.db
├── annotations/                # gitignored
├── samples/                    # gitignored
└── results/                    # gitignored
```

`.gitignore` additions: `evals/traces/`, `evals/annotations/`, `evals/samples/`,
`evals/results/`. Everything else — fixtures, golden set, cache, baselines,
taxonomy, prompts — is **committed**, because those are the artifacts that make the
work reproducible by someone else.

---

## 3. Data models

All models are `pydantic.BaseModel` (pydantic 2 is already a dependency) for free
JSON schema, validation, and migration hooks.

### 3.1 Trace

```python
# evals/trace/models.py
SCHEMA_VERSION = 1

SpanType = Literal[
    "phase_start", "phase_end", "llm_call", "tool_use", "tool_result",
    "guardrail_check", "retry", "error", "human_interrupt", "spend_event",
    "smoke_probe", "subagent_start", "subagent_stop",
]

class Span(BaseModel):
    span_id: str
    parent_span_id: str | None = None
    type: SpanType
    t_start: datetime
    t_end: datetime | None = None
    agent_role: str | None = None          # "fullstack_developer", "qa_engineer", ...
    phase: str | None = None               # "planning" | "development" | ...
    payload: dict[str, Any] = Field(default_factory=dict)

    @property
    def duration_s(self) -> float | None: ...

class Artifact(BaseModel):
    path: str                              # relative to workspace root
    size_bytes: int
    sha256: str
    kind: Literal["source", "test", "doc", "config", "log", "other"]

class CostRecord(BaseModel):
    usd: float | None
    input_tokens: int | None
    output_tokens: int | None
    source: Literal["sdk_reported", "provider_usage", "token_estimate", "unknown"]
    per_model: dict[str, float] = Field(default_factory=dict)

class Provenance(BaseModel):
    git_sha: str
    git_dirty: bool
    taxonomy_version: str
    harness_version: str
    pricing_table_version: str
    python_version: str
    platform: str
    seed: int | None
    tier: Literal["A", "B", "C"]
    scenario_content_sha256: str
    model_ids: dict[str, str]              # role -> model id actually used

class Trace(BaseModel):
    schema_version: int = SCHEMA_VERSION
    trace_id: str
    scenario_id: str
    backend: Literal["crewai", "langgraph", "claude-agent-sdk"]
    status: Literal["complete", "failed", "awaiting_human", "killed", "budget_abort"]
    started_at: datetime
    ended_at: datetime | None
    spans: list[Span]
    artifacts: list[Artifact]
    cost: CostRecord
    provenance: Provenance
    warnings: list[str] = Field(default_factory=list)
    raw_result: dict[str, Any] = Field(default_factory=dict)   # backend's own dict, verbatim

    # --- query helpers used pervasively by checks ---
    def spans_of(self, *types: SpanType) -> list[Span]: ...
    def phases(self) -> list[str]: ...
    def phase_repeats(self) -> dict[tuple[str, str | None], int]: ...
    def errors(self) -> list[Span]: ...
    def files(self, kind: str | None = None) -> list[Artifact]: ...
    def read_artifact(self, path: str) -> str | None: ...    # from sidecar blob store
```

**Artifact contents.** Traces reference workspace files by hash; the bytes live in
`evals/traces/blobs/<sha256[:2]>/<sha256>` (content-addressed, deduplicated). Fixture
traces bundle their blobs. Text files above 256 KB are truncated with a marker; binary
files store hash only. This keeps traces small enough to diff while making
`read_artifact()` work offline — which judges depend on.

### 3.2 Scoring models

```python
# evals/checks/base.py
class CheckResult(BaseModel):
    check_id: str
    failure_mode_id: str | None
    trace_id: str
    outcome: Literal["pass", "fail", "not_applicable", "error"]
    evidence_span_ids: list[str] = []
    evidence_text: str = ""
    detail: dict[str, Any] = {}

class Check(Protocol):
    id: ClassVar[str]
    failure_mode_id: ClassVar[str | None]
    tier: ClassVar[Literal["A", "B", "C"]]
    def run(self, trace: Trace) -> CheckResult: ...
```

```python
# evals/judges/base.py
class JudgeSpec(BaseModel):        # parsed from prompt front matter
    judge_id: str
    version: int
    failure_mode_id: str | None
    question: str                  # the single binary question
    pass_means: str
    fail_means: str
    model: str
    provider: Literal["anthropic", "openrouter"]
    evidence_builder: str          # key into evidence registry
    prompt_hash: str               # sha256 of the file

class Verdict(BaseModel):
    judge_id: str
    prompt_hash: str
    model_id: str
    provider: str
    trace_id: str
    labeling_unit_id: str
    verdict: Literal["pass", "fail", "error"]
    reason: str
    evidence_quote: str
    evidence_sha256: str
    single_vendor: bool
    ensemble: dict[str, Any] | None = None   # spread, contested, per-judge
    cached: bool = False
    latency_ms: int | None = None
```

```python
# evals/alignment.py
class AlignmentReport(BaseModel):
    judge_id: str
    prompt_hash: str
    split: Literal["dev", "test"]
    n: int
    tp: int; fp: int; tn: int; fn: int
    tpr: float; tnr: float; precision: float; f1: float; accuracy: float
    kappa: float
    tpr_ci95: tuple[float, float]
    tnr_ci95: tuple[float, float]
    eligible_to_gate: bool
    ineligibility_reasons: list[str]
    validated_at: datetime
    stale: bool
    disagreements: list[Disagreement]
```

### 3.3 Golden set record

```jsonl
{"labeling_unit_id":"FM-001::todo-api-beginner__crewai__20260703T101500__a1b2::span_0042",
 "trace_id":"todo-api-beginner__crewai__20260703T101500__a1b2",
 "span_id":"span_0042","failure_mode_id":"FM-001","human_label":"present",
 "annotator":"rick","labeled_at":"2026-08-18T14:02:11Z","split":"dev",
 "notes":"dev agent returned markdown fences + 'shall I save these?'; zero tool_use spans in phase"}
```

---

## 4. Component design

### 4.1 L1 — TraceBuilder (R1)

```python
# evals/trace/builder.py
class TraceBuilder:
    def __init__(self, *, scenario: dict, backend: str, tier: str, seed: int | None): ...

    def from_live_run(self, result: Any, workspace: Path, wall_time_s: float) -> Trace: ...
    def from_workspace(self, workspace: Path, *, scenario_id: str | None = None) -> Trace: ...
```

**Parsing strategy.** Each source contributes spans; a merge step sorts by `t_start`
and assigns stable `span_id = f"span_{i:04d}"`.

| Source | Spans produced | Notes |
| --- | --- | --- |
| `logs/phases.jsonl` | `phase_start`, `phase_end`, `retry` | authoritative for the phase timeline |
| `logs/costs.jsonl` | `spend_event`, `llm_call` | carries `usage.cost` / `response_cost` when present → `CostRecord.source = provider_usage` |
| `logs/audit.jsonl` | `tool_use`, `tool_result`, `guardrail_check`, `subagent_start`, `subagent_stop` | Claude SDK hook log; richest source |
| `logs/session.json` | provenance, `session_id`, `total_cost_usd` | → `CostRecord.source = sdk_reported` |
| `state.messages[]` (LangGraph) | `llm_call` with `usage_metadata` | reuses `_extract_total_tokens()` logic from `metrics.py` |
| workspace tree | `Artifact[]` | walk, hash, classify by path (`src/`→source, `tests/`→test, `docs/`→doc) |
| `run_store.py` SQLite | started/ended, status | for retroactive builds where logs are partial |
| smoke report (if present) | `smoke_probe` | boot + HTTP probe results from the runtime smoke gate |

**Backend gaps and how they are handled.** CrewAI and LangGraph do not currently
write `audit.jsonl`; their traces will have no `tool_use` spans. `TraceBuilder`
records `warnings: ["no audit log for backend=crewai; tool-level checks skipped"]`,
and affected checks return `not_applicable` (R5.6) rather than false `pass`. A
follow-up task (Phase 8) adds a minimal audit writer to the two OpenRouter backends so
this asymmetry closes — but the harness must be correct before that lands, not after.

### 4.2 L2 — TraceStore and Sampler (R2)

```python
# evals/store.py
class TraceStore:
    def __init__(self, root: Path = Path("evals/traces")): ...
    def write(self, trace: Trace) -> Path: ...        # refuses overwrite (R1.7)
    def load(self, trace_id: str) -> Trace: ...
    def query(self, **filters) -> list[TraceIndexRow]: ...
    def rebuild_index(self) -> int: ...
    def put_blob(self, data: bytes) -> str: ...       # returns sha256
    def get_blob(self, sha: str) -> bytes | None: ...
```

Index schema:

```sql
CREATE TABLE traces (
  trace_id TEXT PRIMARY KEY, scenario_id TEXT, backend TEXT, status TEXT,
  git_sha TEXT, started_at TEXT, duration_s REAL, cost_usd REAL, cost_source TEXT,
  span_count INT, error_count INT, retry_count INT, file_count INT,
  label_count INT DEFAULT 0, tier TEXT, schema_version INT
);
CREATE INDEX ix_traces_strata ON traces(backend, scenario_id, status);
```

Sampler strategies are pure functions `(rows, n, seed) -> list[trace_id]`. The
`extremes` strategy takes the top ⌈n/3⌉ by each of duration, cost, and retry_count,
deduplicated — this is where the interesting failures cluster.

### 4.3 L2 — Annotation TUI (R3)

A single-file terminal loop using `rich` (already a dependency). No web server, no
new deps. The review pane is generated by `evals/annotate.py::render_trace_card()`,
which is also reused as a judge `evidence_builder` — so the human and the judge see
comparable evidence, which is a prerequisite for meaningful alignment.

Keybindings: `n` next, `p` previous, `t` add tag, `f` mark first-failure span,
`/` search spans, `q` save and quit. Notes are captured via `$EDITOR` for anything
longer than a line.

The saturation counter (R3.6) is displayed live in the footer:
`new tags: 0 for last 14 traces`.

### 4.4 L3 — Taxonomy (R4)

```yaml
# evals/taxonomy/failure_modes.yaml
version: "1.0.0"
failure_modes:
  - id: FM-001
    slug: tool_call_omission
    title: Model emits code as prose instead of calling the write tool
    definition: >
      A development or QA phase ends with the agent having produced syntactically
      valid code inside its message text (fenced or otherwise) while making zero
      successful file-writing tool calls in that phase, leaving the workspace
      without the corresponding file. Asking the user for permission to save counts
      as this failure; there is no user.
    layer: model
    severity: blocker
    detection: check
    implemented_by: [CHK-tool-call-emitted]
    positive_examples:
      - {trace_id: "...", span_id: "span_0042"}
    negative_examples:
      - {trace_id: "...", span_id: "span_0011"}
    references:
      - docs/posts/failure-taxonomy.md#1
    introduced_in: "1.0.0"
    status: active
```

`loader.py` validates on every load and is invoked by a unit test, so a malformed
taxonomy fails CI in under a second.

`COVERAGE.md` generation walks the taxonomy, the check registry, and the judge
directory, and prints an uncovered-FM table. An FM with `detection: check` and no
`implemented_by` entry is a hard validation error, not a warning.

### 4.5 L4 — Checks (R5)

Registration:

```python
# evals/checks/__init__.py
_REGISTRY: dict[str, Check] = {}

def check(*, id: str, failure_mode_id: str | None = None, tier: str = "A"):
    def deco(fn: Callable[[Trace], CheckResult]) -> Callable:
        _REGISTRY[id] = _FunctionCheck(id, failure_mode_id, tier, fn)
        return fn
    return deco

def all_checks(tier: str | None = None) -> list[Check]: ...
```

Representative implementation, showing the evidence discipline every check must follow:

```python
# evals/checks/trajectory.py
@check(id="CHK-tool-call-emitted", failure_mode_id="FM-001")
def tool_call_emitted(trace: Trace) -> CheckResult:
    dev_phases = [s for s in trace.spans_of("phase_end")
                  if s.phase in {"development", "testing"}]
    if not dev_phases:
        return na("CHK-tool-call-emitted", trace, "no development phase in trace")
    if not trace.spans_of("tool_use") and "no audit log" in " ".join(trace.warnings):
        return na("CHK-tool-call-emitted", trace, "backend emits no tool-level audit")

    offenders = []
    for phase in dev_phases:
        writes = [s for s in trace.spans_of("tool_use")
                  if s.phase == phase.phase and _is_write_tool(s)]
        produced = [a for a in trace.files() if a.kind in {"source", "test"}]
        if not writes and _has_fenced_code(phase.payload.get("output", "")):
            offenders.append(phase.span_id)
        elif not writes and not produced:
            offenders.append(phase.span_id)
    ...
```

Helpers `na()`, `passed()`, `failed()` in `checks/base.py` keep every check three
lines from a well-formed `CheckResult`, which is how a registry of thirteen checks
stays consistent.

`CHK-listener-self-trigger` is the odd one out: it introspects
`src/ai_team/flows/main_flow.py` rather than a Trace. It is registered with
`tier="A"` and takes an optional `trace=None`. This preserves the existing meta-test
(taxonomy §2's shipped fix) inside the single reporting surface.

### 4.6 L4 — Guardrail evaluation (R6)

```python
# evals/guardrail_eval.py
from ai_team.guardrails.corpus_metrics import ConfusionCounts, score, format_report

class GuardrailEvaluator:
    def __init__(self, name: str, invoke: Callable[[dict], str]): ...
    def evaluate(self, corpus: list[GuardrailCase]) -> ConfusionCounts:
        outcomes = [(self.invoke(c.input) == "fail", c.label == "violation")
                    for c in corpus]
        return score(outcomes)
    def sweep(self, corpus, param: str, values: list[float]) -> list[tuple[float, ConfusionCounts]]: ...
```

Corpus seeding comes from two sources: synthetic adversarial cases (already partly
present in `evals/backends/test_claude_sdk_eval.py::ADVERSARIAL_INPUTS`) and, more
valuably, **mined from the trace corpus** — every `guardrail_check` span with outcome
`fail` on a run that nonetheless satisfied all acceptance criteria is a false-positive
candidate, surfaced for human labeling. That closes the loop from taxonomy §5 back
into measurement.

`thresholds.yaml`:

```yaml
scope_relevance:   {recall_floor: 0.85, fpr_ceiling: 0.05, min_cases: 40}
role_boundary:     {recall_floor: 0.90, fpr_ceiling: 0.02, min_cases: 40}
security_patterns: {recall_floor: 0.95, fpr_ceiling: 0.10, min_cases: 60}
```

Security gets a high recall floor and a tolerant FPR ceiling; scope relevance the
reverse. Encoding that asymmetry in a file — rather than in one uniform threshold —
is the substantive fix for taxonomy §5.

### 4.7 L4 — Binary judges (R7)

Prompt file format:

```markdown
---
judge_id: fm-001-tool-call-omission
version: 1
failure_mode_id: FM-001
question: Did the agent finish a development phase without writing the code to disk?
pass_means: The agent wrote code to disk via tool calls; no prose-only delivery.
fail_means: The agent produced code only as message text, or asked permission to save.
model: claude-haiku-4-5-20251001
provider: anthropic
evidence_builder: dev_phase_transcript
---

You are auditing one phase of an autonomous software agent's run.

Multi-agent frameworks coordinate through files on disk. Code that appears only in
an agent's message text writes nothing and is a total failure of the phase, even
when the code itself is correct.

## Evidence
{evidence}

## Decision
Answer the single question: {question}

Reply with JSON only:
{"verdict": "pass" | "fail", "reason": "<one sentence>", "evidence_quote": "<≤200 chars quoted verbatim from the evidence>"}
```

`BinaryJudge` reuses `LLMJudge`'s transport (`_check_once_anthropic`,
`_check_once_openrouter`) unchanged — the provider abstraction there is already
correct — and replaces only the parsing and the error contract:

```python
# evals/judges/base.py
class BinaryJudge:
    def __init__(self, spec: JudgeSpec, *, cache: VerdictCache, allow_network: bool): ...

    def judge(self, unit: LabelingUnit, trace: Trace) -> Verdict:
        evidence = EVIDENCE[self.spec.evidence_builder](trace, unit)
        key = sha256(self.spec.prompt_hash + self.spec.model + evidence)
        if (hit := self.cache.get(key)) is not None:
            return hit.model_copy(update={"cached": True})
        if not self.allow_network:
            raise TierAMissingVerdict(key, unit, self.spec)   # R11.4
        ...
```

`evidence_quote` is not decoration. Requiring a verbatim quote from the supplied
evidence gives a cheap, checkable grounding signal: `assert quote in evidence`. A
judge that cannot quote its own evidence is hallucinating, and the harness marks the
verdict `error` rather than trusting it.

**Ensemble.** `EnsembleBinaryJudge` wraps N `BinaryJudge`s across providers, majority-
votes, and records `spread` (fraction disagreeing) and `contested`. R7.6's rule —
a single-vendor verdict cannot settle a cross-backend comparison involving that
vendor — is enforced in `aggregate.py`, not left to the reader.

### 4.8 L3/L5 — Alignment and bias correction (R8)

```python
# evals/alignment.py
def confusion(verdicts: list[Verdict], labels: list[GoldenLabel]) -> tuple[int,int,int,int]:
    """'fail' verdict == predicting the failure mode is PRESENT."""

def cohens_kappa(tp, fp, tn, fn) -> float: ...

def bootstrap_ci(pairs, statistic, *, n_resamples=2000, seed=0) -> tuple[float, float]: ...

def bias_corrected_rate(observed: float, tpr: float, tnr: float) -> float | None:
    denom = tpr + tnr - 1.0
    if denom <= 0.2:
        return None                      # R8.7 — unstable, suppress
    return min(1.0, max(0.0, (observed + tnr - 1.0) / denom))
```

The suppression rule matters more than the formula. Near `TPR + TNR = 1` the judge is
a coin flip and the correction explodes; printing a corrected number there would be
worse than printing nothing. The report says *"judge too weak to correct (TPR+TNR−1 =
0.14); reporting raw rate only"*.

Split assignment is a pure function of the labeling-unit id, so it survives
re-labeling and cannot be gamed by re-running:

```python
def assign_split(labeling_unit_id: str) -> Literal["dev", "test"]:
    return "test" if int(sha256(labeling_unit_id.encode()).hexdigest()[:8], 16) % 100 < 40 else "dev"
```

**Test-split protection (R8.4)** is enforced by recording, in
`evals/golden/.validation_log.jsonl`, one line per `(judge_id, prompt_hash)` that has
touched `test`. A second attempt without `--allow-retest` exits non-zero. This is the
mechanism that keeps the reported TPR honest, and it is the detail that distinguishes
a real eval system from a dashboard.

### 4.9 L5 — Reliability (R9)

```python
# evals/reliability.py
def pass_at_k(outcomes: Sequence[bool]) -> float: return float(any(outcomes))
def pass_pow_k(outcomes: Sequence[bool]) -> float: return float(all(outcomes))
def pass_rate(outcomes) -> float: return sum(outcomes) / len(outcomes)
def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]: ...
def is_flaky(outcomes) -> bool: return 0 < sum(outcomes) < len(outcomes)
def indistinguishable(a: CellResult, b: CellResult) -> bool:   # R9.5
    return _overlaps(wilson_ci(a.successes, a.n), wilson_ci(b.successes, b.n))
```

Wilson rather than normal-approximation because at `k=3` the normal interval is
nonsense (and can extend below zero). With `n=3`, a 3/3 result has a Wilson 95% CI of
roughly `[0.44, 1.00]` — which is precisely the humility the report needs to carry.

### 4.10 L5 — Cost (R10)

```yaml
# evals/pricing.yaml
version: "2026-08-16"
models:
  claude-haiku-4-5-20251001: {input_per_mtok: 1.00, output_per_mtok: 5.00}
  anthropic/claude-sonnet-4:  {input_per_mtok: 3.00, output_per_mtok: 15.00}
  deepseek/deepseek-v3:       {input_per_mtok: 0.27, output_per_mtok: 1.10}
# NOTE: verify against provider pricing pages at implementation time and stamp
# `version` with the date checked. A stale rate table silently corrupts every
# token_estimate cost, so `pricing_table_version` is carried in provenance (R14.1).
```

`BudgetLedger` is process-local and per-suite-run — deliberately *not* a global
singleton, because taxonomy §7 records exactly that bug (`SpendGuard` cross-
contaminating concurrent runs). The ledger is threaded through `run_evals.py` as an
explicit parameter.

### 4.11 L6 — Gate and report (R12, R13)

```python
# evals/gate.py
class GateDecision(BaseModel):
    passed: bool
    regressions: list[Regression]
    warnings: list[Regression]
    improvements: list[str]
    suppressed: list[str]     # non-gating (advisory judges, provisional guardrails)

def evaluate_gate(report: SuiteReport, baseline: Baseline) -> GateDecision: ...
```

Exit codes: `0` pass, `1` regression, `2` harness error (missing cache, malformed
taxonomy, budget abort). CI distinguishes these — a harness error must not read as a
product regression.

The HTML report is a single self-contained file, no CDN, generated with Jinja2
(already a dependency). Charts are inline SVG built by hand — a stacked bar of
failure incidence by taxonomy layer, and a precision-recall curve per guardrail. The
layer chart is the one worth building well: it is the visual form of the taxonomy
essay's central claim, now measured rather than asserted.

---

## 5. Execution tiers and cost model

| | Tier A | Tier B | Tier C |
| --- | --- | --- | --- |
| Trigger | every PR | nightly cron | manual / pre-release |
| Source | `evals/fixtures/traces/` | live runs | live runs |
| Network to model APIs | **blocked** | allowed | allowed |
| Judges | cache only | live + cache | live + cache |
| k | 1 | 3 | 5 |
| Scenarios | all fixtures | `smoke-test`, `todo-api-beginner` | all |
| Backends | all (from fixtures) | all 3 | all 3 |
| Wall clock | < 120 s | ~40 min | ~3 h |
| **Model spend** | **$0.00** | **≤ $2.00** | **≤ $5.00 (hard ceiling)** |

### 5.1 Tier B budget derivation

| Item | Count | Unit | Subtotal |
| --- | --- | --- | --- |
| `smoke-test` runs | 3 backends × k=3 = 9 | ~$0.04 | $0.36 |
| `todo-api-beginner` runs | 3 backends × k=1 = 3 | ~$0.25 | $0.75 |
| Binary judges (haiku-class, ~1.2k in / 80 out) | ~14 units × 12 traces = 168 calls | ~$0.0016 | $0.27 |
| Second-vendor ensemble judge on gating FMs only | ~60 calls | ~$0.0020 | $0.12 |
| Slack for retries and re-judging | — | — | $0.20 |
| **Total** | | | **≈ $1.70** |

Headroom to the $2.00 tier budget: ~15%. Headroom to the $5.00 hard ceiling: ~66%.
`AI_TEAM_SKIP_POST_RUN=1` and `MEMORY_MEMORY_ENABLED=false` (already set by
`run_evals._make_env`) stay set — they save both time and tokens.

The single biggest cost lever is **cache hit rate on judges**. Because evidence is
built deterministically from immutable traces, re-scoring an unchanged corpus after a
prompt-unchanged code change costs $0.00. Only new traces and bumped prompt versions
spend.

---

## 6. Error handling

| Condition | Behaviour |
| --- | --- |
| Missing / truncated log file | Trace built anyway; `warnings[]` entry; dependent checks → `not_applicable` (R1.6, R5.6) |
| Trace id collision | Hard error, no overwrite (R1.7) |
| Unknown `schema_version` | Attempt registered migration; else raise `TraceSchemaError` naming the migration (R14.3) |
| Judge JSON unparseable after 3 attempts | `verdict: "error"`, excluded from denominators, surfaced in report (R7.9) |
| `evidence_quote` not found in evidence | `verdict: "error"` + `reason: "ungrounded"`; counted separately as a judge-health metric |
| Tier A cache miss | `TierAMissingVerdict`, exit 2, message names the key and the `cache warm` command (R11.4) |
| Budget ceiling crossed | Remaining runs `skipped_budget`; suite exits 2; partial report still written (R10.3) |
| Guardrail corpus below `min_cases` | Metrics computed but marked `provisional`; excluded from gate (R6.4) |
| Judge below eligibility | Verdicts recorded, excluded from gate, listed under `suppressed` (R8.6, R12.3) |
| Dirty working tree | Runs; `git_dirty: true`; `baseline accept` refused (R14.2) |
| Backend hangs | Existing `run_evals.py` watchdogs (drain 90 s, log-freeze 120 s) unchanged; killed run still emits a trace with `status: "killed"` |

The governing principle: **the harness never silently converts "I don't know" into
"pass" or into "fail"**. Both directions corrupt the numbers, and the second one —
the current `LLMJudge` error behaviour — is the more insidious because it looks
conservative while inflating the measured failure rate.

---

## 7. Testing strategy

The eval system needs its own evals. Three levels:

### 7.1 Unit tests — `tests/unit/evals/`

- Taxonomy loader: valid file loads; each invalid variant (duplicate id, bad enum,
  dangling trace ref, `detection: check` with no `implemented_by`) raises.
- Every check against a synthetic `Trace` fixture: one crafted to fail, one to pass,
  one to return `not_applicable`. **A check with no failing fixture is not merged** —
  an untested check that never fires is worse than no check.
- `alignment.py`: known confusion matrices → hand-computed TPR/TNR/κ; bootstrap CI
  determinism under fixed seed; `bias_corrected_rate` returns `None` at the
  suppression boundary and is exact for `TPR=TNR=1.0`.
- `reliability.py`: Wilson CI against published values; `pass^k` at k=1,3,5.
- `cost.py`: each `source` path; budget abort fires exactly at ceiling.
- Split assignment: stable across runs, ~40/60 distribution over 10k synthetic ids.

### 7.2 Mutation testing of the check suite — `tests/unit/evals/test_check_sensitivity.py`

For each check, take a passing fixture trace, apply a targeted mutation that
introduces the failure mode, and assert the check flips to `fail`. Mutations:
delete all `tool_use` spans (FM-001); duplicate a `phase_start` five times (FM-002);
inject a 4,000 s gap after `human_interrupt` (FM-003); set `cost.usd` above budget
(FM-007); inject a `ModuleNotFoundError` test span (FM-010). This is the closest
thing to a ground truth for "does this harness actually detect anything", and it is
cheap and deterministic.

### 7.3 Integration — `tests/integration/evals/`

- `TraceBuilder.from_workspace()` against a committed miniature workspace containing
  all four log types, asserting exact span counts and cost source.
- Full Tier A pipeline on `evals/fixtures/traces/`, asserting determinism (R11.5) by
  running twice and diffing `report.json` modulo `generated_at`.
- Gate: synthetic report + baseline pairs covering each row of the R12.2 table.
- Network isolation: Tier A run under a `socket` monkeypatch that raises on connect.

### 7.4 What is deliberately not tested automatically

Judge quality. That is what the golden set and R8 alignment are for, and it is
measured, not asserted. `tests/` must never contain an assertion of the form
`assert judge_score >= 0.7`.

---

## 8. Migration and sequencing risk

The refactor touches files the current eval workflow depends on. Mitigations:

1. **Additive first.** Phases 1–3 add `evals/trace/`, `evals/store.py`,
   `evals/taxonomy/`, `evals/checks/` without editing `fixtures.py`, `metrics.py`, or
   `run_evals.py`. The existing workflow keeps working untouched through Phase 3.
2. **Trace emission is a side effect before it is a dependency.** Phase 4 makes
   `run_evals.py` write traces; nothing reads them for gating yet. If trace building
   is wrong, evals still run.
3. **`compute_metrics()` is not deleted.** Phase 6 makes checks the source of truth
   and reduces `compute_metrics()` to a thin adapter that delegates, so
   `format_scorecard()` and the three backend test files keep their contract.
4. **The gate lands last and starts permissive.** Phase 9 ships the gate in
   `--warn-only` mode for one week of nightlies before it can fail a build.

The one irreversible decision is the Trace schema. Get `SCHEMA_VERSION = 1` reviewed
before Phase 4 emits traces at volume, because retroactive rebuilds are cheap only
while the corpus is small.

---

## 9. Interview-facing summary

Three sentences, because this is a portfolio artifact as much as an engineering one:

> The eval harness separates execution from scoring at a Trace boundary, so every
> past run of the system becomes free, replayable evidence and a pull request can be
> gated for zero model spend. Its failure taxonomy is not a checklist — it is ten
> failure classes observed in production runs, each with a deterministic check bound
> to it by ID, so what the suite measures cannot drift from what actually broke.
> Where a question needs a model to answer it, the judge is binary, its prompt is a
> versioned file, and it is not allowed to gate anything until it clears TPR ≥ 0.90
> and TNR ≥ 0.90 against a held-out split of my own labels — and the rates it reports
> are bias-corrected using those measured error rates.

The follow-up question this invites is *"what's your judge's TPR?"* — and after
Phase 7 there is a number, with a confidence interval, in a committed file.
