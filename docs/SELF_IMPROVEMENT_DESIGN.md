# Self-Improvement: Design & Task List

> Companion to [SELF_IMPROVEMENT_AUDIT.md](SELF_IMPROVEMENT_AUDIT.md). This document is the implementation blueprint.

---

## Table of Contents

0. [Design Principles](#0-design-principles)
1. [Run Record & Audit Trail](#1-run-record--audit-trail)
2. [Auto-Extract Lessons](#2-auto-extract-lessons)
3. [Lesson Deduplication, TTL & Caps](#3-lesson-deduplication-ttl--caps)
4. [Quality Metrics Persistence](#4-quality-metrics-persistence)
5. [Lesson Effectiveness Tracking](#5-lesson-effectiveness-tracking)
6. [Guardrail Calibration](#6-guardrail-calibration)
7. [Extended Backend Comparison](#7-extended-backend-comparison)
8. [Cross-Backend Token Tracking](#8-cross-backend-token-tracking)
9. [Budget Enforcement](#9-budget-enforcement)
10. [RAG Lesson Ingestion](#10-rag-lesson-ingestion)
11. [Metrics Dashboard CLI](#11-metrics-dashboard-cli)
12. [Implementation Tasks](#12-implementation-tasks)

---

## 0. Design Principles

1. **Zero-config improvement.** Self-improvement must work out of the box. No manual CLI, no cron, no wrapper scripts. An org installs, runs, and the system gets better.
2. **Measure everything, abort nothing (by default).** Every signal is captured. Budget enforcement and lesson injection are configurable, never silently destructive.
3. **Shared schema, backend-agnostic.** All metrics, lessons, and run records use the same SQLite/Postgres tables regardless of backend. Adding a backend never requires schema changes.
4. **Deterministic where possible.** Lesson extraction, deduplication, calibration, and metrics aggregation are pure functions over SQL data. No LLM in the critical path of self-improvement.
5. **Graceful degradation preserved.** Every self-improvement call remains wrapped in `try/except`. A broken lesson store never breaks a run.

---

## 1. Run Record & Audit Trail

### Problem

No durable, queryable record of runs exists. The TUI is ephemeral. `events.jsonl` is per-project, not aggregated. There is no way to answer "what happened across the last 50 runs?"

### Design

Add a `run_records` table to the existing `LongTermStore` SQLite database (same `data/memory.db` file). One row per run.

#### Schema

```sql
CREATE TABLE IF NOT EXISTS run_records (
    id TEXT PRIMARY KEY,                    -- run_id (UUID)
    started_at TEXT NOT NULL,               -- ISO 8601
    finished_at TEXT,                       -- ISO 8601, NULL if still running
    backend TEXT NOT NULL,                  -- crewai | langgraph | claude-sdk
    team_profile TEXT NOT NULL,             -- full | backend-api | prototype | ...
    env TEXT NOT NULL,                      -- dev | test | prod
    description TEXT,                       -- project description (first 500 chars)
    success INTEGER NOT NULL DEFAULT 0,     -- 0 or 1
    current_phase TEXT,                     -- final phase reached
    duration_sec REAL,                      -- wall-clock seconds
    total_tokens INTEGER DEFAULT 0,         -- prompt + completion
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    estimated_cost_usd REAL DEFAULT 0.0,    -- from token tracker
    phases_completed TEXT,                  -- JSON array of phase names
    retry_count INTEGER DEFAULT 0,          -- total retries across all phases
    guardrail_pass_count INTEGER DEFAULT 0,
    guardrail_fail_count INTEGER DEFAULT 0,
    guardrail_warn_count INTEGER DEFAULT 0,
    lessons_injected INTEGER DEFAULT 0,     -- how many lessons were active this run
    lessons_effective INTEGER DEFAULT 0,    -- how many prevented a recurrence
    files_generated INTEGER DEFAULT 0,
    code_quality_score REAL,                -- 0-100, NULL if not measured
    test_pass_count INTEGER DEFAULT 0,
    test_fail_count INTEGER DEFAULT 0,
    error_summary TEXT,                     -- first 1000 chars of error
    metadata TEXT                           -- JSON blob for backend-specific data
);
CREATE INDEX IF NOT EXISTS idx_run_records_backend ON run_records(backend);
CREATE INDEX IF NOT EXISTS idx_run_records_started ON run_records(started_at);
```

#### Write Points

Each backend's `run()` method wraps execution:

```python
# Pseudocode — applies to all backends
record = RunRecord(id=run_id, started_at=now(), backend=name, ...)
try:
    result = _execute_pipeline(...)
    record.success = result.success
    record.duration_sec = elapsed
    record.update_from_state(state)  # extract quality scores, retries, etc.
finally:
    record.finished_at = now()
    store.save_run_record(record)
```

#### Read Points

- `scripts/show_runs.py` — CLI to list/filter/export run records
- `scripts/show_metrics.py` — aggregate metrics from run records
- `ComparisonReport.from_run_records()` — comparison uses stored records instead of live-only snapshots
- Web dashboard / TUI — future metrics tab

### Files to Modify

| File | Change |
|------|--------|
| `src/ai_team/memory/memory_config.py` | Add `run_records` table to `LongTermStore._init_schema()`, add `save_run_record()` and `get_run_records()` methods |
| `src/ai_team/memory/run_record.py` | **New.** `RunRecord` dataclass, `RunRecordWriter` context manager |
| `src/ai_team/flows/main_flow.py` | Wrap `kickoff()` with RunRecordWriter |
| `src/ai_team/backends/langgraph_backend/backend.py` | Wrap `run()` with RunRecordWriter |
| `src/ai_team/backends/crewai_backend/backend.py` | Wrap `run()` with RunRecordWriter (if separate from flow) |
| `scripts/show_runs.py` | **New.** CLI for querying run records |

---

## 2. Auto-Extract Lessons

### Problem

`extract_lessons()` must be invoked manually via `scripts/extract_lessons.py`. Without it, failure records accumulate but lessons are never promoted. The loop is open by default.

### Design

Call `extract_lessons()` at the **start** of every run, before graph/crew compilation, gated by a config flag.

```python
# In each backend's run() method, before building agents:
if settings.self_improvement.auto_extract:
    from ai_team.memory.lessons import extract_lessons
    with contextlib.suppress(Exception):
        extract_lessons(promote_threshold=settings.self_improvement.promote_threshold)
```

#### Configuration

Add to `settings.py`:

```python
class SelfImprovementSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_TEAM_SI_", extra="ignore")

    auto_extract: bool = Field(default=True, description="Auto-extract lessons at run startup")
    promote_threshold: int = Field(default=2, ge=1, description="Min occurrences to promote a lesson")
    max_lessons_per_role: int = Field(default=10, ge=1, description="Max lessons injected per agent role")
    lesson_ttl_days: int = Field(default=90, ge=1, description="Expire lessons older than this")
    track_effectiveness: bool = Field(default=True, description="Track lesson hit/miss rates")
    auto_calibrate: bool = Field(default=False, description="Auto-calibrate guardrails (requires --approve-overrides for production)")
```

#### Cost

One SQLite read (~ms). Zero LLM calls. Risk: near zero.

### Files to Modify

| File | Change |
|------|--------|
| `src/ai_team/config/settings.py` | Add `SelfImprovementSettings`, wire into `get_settings()` |
| `src/ai_team/flows/main_flow.py` | Call `extract_lessons()` in `_pre_run_setup()` or equivalent |
| `src/ai_team/backends/langgraph_backend/backend.py` | Call `extract_lessons()` at top of `run()` |

---

## 3. Lesson Deduplication, TTL & Caps

### Problem

Each `extract_lessons()` call appends new lesson rows without checking if the same clustering key exists. Duplicates accumulate. No expiry. No cap per role.

### Design

#### 3a. Upsert Semantics

Change `extract_lessons()` to check for existing lessons with the same `lesson_id` (clustering key) before inserting:

```python
def _upsert_lesson(store: LongTermStore, lesson: dict) -> bool:
    """Insert if new, update evidence_count + last_seen if existing. Returns True if new."""
    existing = store.get_patterns(pattern_type=LESSON_PATTERN_TYPE, limit=500)
    for row in existing:
        data = json.loads(row["content"])
        if data.get("lesson_id") == lesson["lesson_id"]:
            # Update in place: increment evidence_count, update last_seen
            data["evidence_count"] = max(data["evidence_count"], lesson["evidence_count"])
            data["last_seen"] = lesson["created_at"]
            store.update_pattern(row["id"], json.dumps(data))
            return False
    store.add_pattern(LESSON_PATTERN_TYPE, json.dumps(lesson))
    return True
```

This requires adding `update_pattern(id, content)` to `LongTermStore`.

#### 3b. TTL Expiry

In `load_role_lessons()`, filter out lessons where `created_at` (or `last_seen`) is older than `lesson_ttl_days`:

```python
cutoff = (datetime.now(UTC) - timedelta(days=settings.self_improvement.lesson_ttl_days)).isoformat()
lessons = [l for l in lessons if (l.last_seen or l.created_at) >= cutoff]
```

Also apply TTL in `LongTermStore.apply_retention()` — already deletes by `created_at`, but lessons should use `last_seen` (a recently-confirmed lesson shouldn't expire even if first created 120 days ago).

#### 3c. Per-Role Cap

In `load_role_lessons()`, after filtering by role and TTL, sort by `evidence_count` descending and truncate to `max_lessons_per_role`:

```python
lessons.sort(key=lambda l: l.evidence_count, reverse=True)
return lessons[:settings.self_improvement.max_lessons_per_role]
```

#### Metrics

- `prompt_lesson_tokens` — count tokens added by lessons per agent. Log as structured event.
- Should plateau after initial accumulation, not grow linearly.

### Files to Modify

| File | Change |
|------|--------|
| `src/ai_team/memory/memory_config.py` | Add `LongTermStore.update_pattern(id, content)` method |
| `src/ai_team/memory/lessons.py` | Replace `store.add_pattern()` with `_upsert_lesson()` in `extract_lessons()`; add `last_seen` field to lesson schema; apply TTL and cap in `load_role_lessons()` |
| `src/ai_team/memory/lessons.py` | Add `Lesson.last_seen` field to dataclass |

---

## 4. Quality Metrics Persistence

### Problem

`performance_metrics` table exists but has zero writers. Code quality scores, test results, and guardrail outcomes computed during runs vanish.

### Design

Add a `record_quality_metrics()` function that writes to `performance_metrics` at the end of each phase or at finalize. The existing `LongTermStore.add_metric()` API is sufficient — it just has no callers.

#### What to Record

| Metric Name | Source | When |
|-------------|--------|------|
| `code_quality_score` | `quality.code_quality_guardrail()` result `.score` | End of development phase |
| `test_pass_rate` | `state.test_results.tests.ok` | End of testing phase |
| `lint_pass` | `state.test_results.lint.ok` | End of testing phase |
| `guardrail_pass_rate` | Ratio of pass / (pass + fail) per guardrail type | End of run |
| `retry_count` | `state.retry_counts` sum | End of run |
| `phase_duration_sec` | `state.phase_history` timestamps | End of each phase |

#### Implementation

```python
# src/ai_team/memory/metrics.py (new)

def record_quality_metrics(
    *,
    run_id: str,
    backend: str,
    state: Any,
    store: LongTermStore,
) -> int:
    """Extract and persist quality metrics from final state. Returns count written."""
    count = 0
    d = _to_dict(state)

    # Code quality score (if guardrail was run)
    quality_score = d.get("metadata", {}).get("code_quality_score")
    if quality_score is not None:
        store.add_metric("pipeline", backend, "code_quality_score", float(quality_score))
        count += 1

    # Test results
    tr = d.get("test_results") or {}
    if isinstance(tr, dict):
        tests = tr.get("tests") or {}
        if isinstance(tests, dict) and "ok" in tests:
            store.add_metric("qa_engineer", backend, "test_pass", 1.0 if tests["ok"] else 0.0)
            count += 1
        lint = tr.get("lint") or {}
        if isinstance(lint, dict) and "ok" in lint:
            store.add_metric("qa_engineer", backend, "lint_pass", 1.0 if lint["ok"] else 0.0)
            count += 1

    # Retry count
    retry_counts = d.get("retry_counts") or {}
    if isinstance(retry_counts, dict):
        total_retries = sum(retry_counts.values())
        store.add_metric("pipeline", backend, "retry_count", float(total_retries))
        count += 1

    return count
```

#### Wire Into Both Backends

Call `record_quality_metrics()` right after `record_run_failures()` — same location, same state object.

#### Extend `performance_metrics` Schema

The existing schema is:

```sql
(id, agent_role, model, metric_name, value, created_at)
```

This is sufficient but `model` is awkward for pipeline-level metrics. Use `backend` in the `model` column for now; a future migration can add a dedicated `run_id` column.

Better: add `run_id` and `backend` columns now:

```sql
ALTER TABLE performance_metrics ADD COLUMN run_id TEXT;
ALTER TABLE performance_metrics ADD COLUMN backend TEXT;
```

Handle gracefully if columns already exist (SQLite PRAGMA check).

### Files to Create/Modify

| File | Change |
|------|--------|
| `src/ai_team/memory/metrics.py` | **New.** `record_quality_metrics()` function |
| `src/ai_team/memory/memory_config.py` | Extend `performance_metrics` schema with `run_id`, `backend` columns; add `add_metric()` overload accepting these |
| `src/ai_team/flows/main_flow.py` | Call `record_quality_metrics()` in `finalize_project()` |
| `src/ai_team/backends/langgraph_backend/backend.py` | Call `record_quality_metrics()` after `record_run_failures()` |

---

## 5. Lesson Effectiveness Tracking

### Problem

Lessons are promoted based on occurrence count only. A lesson that fires 5 times but never prevents the failure is still injected forever.

### Design

Track two counters per lesson:

```json
{
  "lesson_id": "...",
  "injected_count": 7,     // how many runs this lesson was active
  "effective_count": 5,     // runs where the corresponding failure did NOT recur
  "ineffective_count": 2,   // runs where it DID recur despite the lesson
  "status": "active"        // active | ineffective | expired
}
```

#### Logic

At the **end** of each run:

1. Load all lessons that were injected this run (from the `lessons_injected` list recorded at startup).
2. For each lesson, check if the corresponding failure pattern (`lesson_id` matches clustering key) recurred in this run's `failure_records`.
3. If recurred: increment `ineffective_count`.
4. If not recurred: increment `effective_count`.
5. If `ineffective_count >= 3` and `effective_count == 0`: set `status = "ineffective"`, stop injecting.

#### Load-Time Filter

In `load_role_lessons()`:

```python
lessons = [l for l in lessons if l.status == "active"]
```

#### Metrics

- `lesson_effectiveness_rate` = effective_count / injected_count per lesson
- Aggregate across all lessons for a dashboard number

### Files to Modify

| File | Change |
|------|--------|
| `src/ai_team/memory/lessons.py` | Add `injected_count`, `effective_count`, `ineffective_count`, `status` fields to lesson schema; add `record_lesson_outcomes()` function; filter by `status` in `load_role_lessons()` |
| `src/ai_team/memory/lessons.py` | Add `get_injected_lessons_for_run()` helper that records which lessons were loaded at startup |
| `src/ai_team/flows/main_flow.py` | Call `record_lesson_outcomes()` at finalize |
| `src/ai_team/backends/langgraph_backend/backend.py` | Call `record_lesson_outcomes()` after run |

---

## 6. Guardrail Calibration

### Problem

The behavioral guardrail's false-positive rate on demo-01 was 100%. No mechanism exists to tune guardrails from observed data.

### Design

A two-stage approach: **detection** (automatic) + **application** (requires opt-in).

#### Stage 1: False-Positive Detection

Track `(guardrail_name, agent_role, violation_key)` tuples with outcomes in the failure journal. The extraction step computes:

```python
def detect_false_positives(*, min_occurrences: int = 3) -> list[dict]:
    """
    A guardrail firing is likely a false positive when:
    1. The same (guardrail, role, violation_key) tuple appears in 3+ runs
    2. AND at least one run with this tuple eventually succeeded
       (either via retry in the same run, or a subsequent run with a lesson)
    """
```

#### Stage 2: Override File

Write `data/guardrail_overrides.yaml`:

```yaml
# Auto-generated by calibrate_guardrails(). Review before applying.
# Set AI_TEAM_SI_AUTO_CALIBRATE=true to apply automatically.
overrides:
  - guardrail: role_adherence
    agent_role: qa_engineer
    violation_pattern: "should only write test code"
    action: downgrade_to_warn    # fail → warn
    evidence_count: 5
    false_positive_rate: 0.80
    last_seen: "2026-04-01T12:00:00Z"
```

#### Stage 3: Application

In `guardrails/behavioral.py`, before returning `status="fail"`:

```python
overrides = _load_guardrail_overrides()
for override in overrides:
    if override.matches(guardrail_name, agent_role, violation_key):
        if override.action == "downgrade_to_warn":
            result.status = "warn"
            result.message += f" [downgraded by calibration: {override.evidence_count} false positives]"
            break
```

#### Safety

- `auto_calibrate` defaults to `False`
- Even when enabled, only `downgrade_to_warn` is supported (never `ignore`)
- The override file is YAML, human-reviewable, version-controllable
- `scripts/calibrate_guardrails.py` CLI with `--dry-run` and `--approve` flags

### Files to Create/Modify

| File | Change |
|------|--------|
| `src/ai_team/memory/lessons.py` | Add `detect_false_positives()` function |
| `src/ai_team/guardrails/calibration.py` | **New.** `calibrate_guardrails()`, `load_guardrail_overrides()`, `GuardrailOverride` dataclass |
| `src/ai_team/guardrails/behavioral.py` | Check overrides before returning `fail` in `role_adherence_guardrail()` |
| `data/guardrail_overrides.yaml` | **New.** Auto-generated, gitignored (add to `.gitignore`) |
| `scripts/calibrate_guardrails.py` | **New.** CLI wrapper with `--dry-run` and `--approve` |
| `.gitignore` | Add `data/guardrail_overrides.yaml` |

---

## 7. Extended Backend Comparison

### Problem

`BackendRunSnapshot` captures only success, duration, phase, and file count. Cannot support the project's evaluation claims.

### Design

Extend `BackendRunSnapshot` and `ComparisonReport` to include cost, quality, and statistical data.

#### Extended Snapshot

```python
class BackendRunSnapshot(BaseModel):
    # Existing fields (unchanged)
    backend_name: str
    team_profile: str
    success: bool
    duration_sec: float
    error: str | None = None
    thread_id: str | None = None
    current_phase: str | None = None
    generated_files_count: int = 0

    # --- NEW FIELDS ---
    # Cost
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0

    # Quality
    code_quality_score: float | None = None
    test_pass_count: int = 0
    test_fail_count: int = 0
    lint_passed: bool | None = None

    # Reliability
    guardrail_pass_count: int = 0
    guardrail_fail_count: int = 0
    guardrail_warn_count: int = 0
    retry_count: int = 0

    # Timing
    phase_durations: dict[str, float] = Field(default_factory=dict)

    # Lessons
    lessons_injected: int = 0
    lessons_effective: int = 0

    # Output fingerprint
    output_file_hashes: dict[str, str] = Field(default_factory=dict)
```

#### Multi-Run Comparison

Add `--runs N` flag to `compare_backends.py`:

```python
class MultiRunComparisonReport(BaseModel):
    demo_path: str
    team_profile: str
    env: str | None
    runs_per_backend: int
    backends: dict[str, list[BackendRunSnapshot]]  # backend_name -> [snapshots]

    def summary_stats(self) -> dict[str, dict[str, float]]:
        """Mean, std, min, max for each metric per backend."""

    def to_markdown(self) -> str:
        """Side-by-side table with means ± std."""
```

#### Populate from RunRecord

When `run_records` exist, `snapshot_from_project_result()` pulls quality/cost data from the run record rather than only from the raw state dict.

### Files to Modify

| File | Change |
|------|--------|
| `src/ai_team/models/comparison_report.py` | Extend `BackendRunSnapshot` with new fields; add `MultiRunComparisonReport`; update `to_markdown()` and `snapshot_from_project_result()` |
| `src/ai_team/utils/backend_comparison.py` | Support `--runs N` flag; aggregate results |
| `scripts/compare_backends.py` | Add `--runs` argument |

---

## 8. Cross-Backend Token Tracking

### Problem

`TokenTracker` is CrewAI-only (uses `crewai.hooks`). LangGraph and Claude SDK have no token tracking.

### Design

#### LangGraph

LangChain models return `usage_metadata` in response objects. Add a callback handler:

```python
# src/ai_team/backends/langgraph_backend/token_callback.py (new)

from langchain_core.callbacks import BaseCallbackHandler

class TokenTrackingCallback(BaseCallbackHandler):
    def __init__(self, tracker: TokenTracker):
        self.tracker = tracker

    def on_llm_end(self, response, **kwargs):
        # Extract usage from response.llm_output or response.generations
        usage = response.llm_output.get("usage", {}) if response.llm_output else {}
        role = kwargs.get("tags", ["unknown"])[0]  # tag agents with role
        self.tracker.record(
            role=role,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            cost=self._compute_cost(role, usage),
        )
```

Attach to the `ChatOpenAI` model in `langgraph_chat.py`:

```python
model = ChatOpenAI(..., callbacks=[TokenTrackingCallback(tracker)])
```

#### Claude Agent SDK (Future)

The Anthropic API returns `usage` in every response:

```python
# response.usage.input_tokens, response.usage.output_tokens
tracker.record(role=agent_role, input_tokens=..., output_tokens=..., cost=...)
```

Wire into the SDK backend's agent loop callback / `StreamEvent` handler.

#### Unified Interface

`TokenTracker` already has a backend-agnostic `record()` method. Each backend provides its own hook/callback that calls `record()`.

### Files to Create/Modify

| File | Change |
|------|--------|
| `src/ai_team/backends/langgraph_backend/token_callback.py` | **New.** `TokenTrackingCallback` for LangChain |
| `src/ai_team/backends/langgraph_backend/graphs/langgraph_chat.py` | Attach callback to `ChatOpenAI` |
| `src/ai_team/backends/langgraph_backend/backend.py` | Initialize `TokenTracker`, pass to model factory, save report after run |
| `src/ai_team/config/token_tracker.py` | Add `register_langchain_callback()` method as convenience |

---

## 9. Budget Enforcement

### Problem

`TokenTracker` logs a warning when cost exceeds `AI_TEAM_MAX_COST_PER_RUN` but does not abort. A runaway run can burn budget.

### Design

Add configurable enforcement behavior:

```python
class BudgetSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_TEAM_BUDGET_", extra="ignore")

    max_cost_per_run: float = Field(default=10.0, description="USD limit per run")
    exceeded_action: Literal["log", "warn", "abort"] = Field(
        default="warn",
        description="What to do when budget is exceeded: log (structlog only), warn (log + console), abort (raise BudgetExceededError)"
    )
```

In `TokenTracker.record()`:

```python
if total > self._max_cost:
    if self._action == "abort":
        raise BudgetExceededError(
            f"Run cost ${total:.2f} exceeds limit ${self._max_cost:.2f}. "
            "Set AI_TEAM_BUDGET_EXCEEDED_ACTION=warn to continue."
        )
    elif self._action == "warn":
        logger.warning("token_tracker_over_budget", ...)
        console.print(f"[bold red]Budget exceeded: ${total:.2f} / ${self._max_cost:.2f}[/]")
    else:
        logger.info("token_tracker_over_budget", ...)
```

`BudgetExceededError` is caught by the backend's `run()` method, which records it in the run record and returns a failed `ProjectResult`.

### Files to Modify

| File | Change |
|------|--------|
| `src/ai_team/config/settings.py` | Add `BudgetSettings` |
| `src/ai_team/config/token_tracker.py` | Add `BudgetExceededError`; implement `exceeded_action` logic in `record()` |
| `src/ai_team/flows/main_flow.py` | Catch `BudgetExceededError` in flow execution |
| `src/ai_team/backends/langgraph_backend/backend.py` | Catch `BudgetExceededError` |

---

## 10. RAG Lesson Ingestion

### Problem

Lessons are injected via direct prompt append (Level 1 — deterministic). Level 2 (semantic RAG retrieval based on project context) is designed but not implemented.

### Design

Add `ingest_lessons()` to `RAGPipeline`:

```python
def ingest_lessons(self, lessons: list[Lesson]) -> int:
    """Ingest promoted lessons into RAG ChromaDB for semantic retrieval."""
    chunks = []
    for lesson in lessons:
        chunks.append(TextChunk(
            text=f"[Lesson for {lesson.agent_role}] {lesson.title}: {lesson.text}",
            source_id=f"lesson:{lesson.lesson_id}",
            metadata={
                "type": "lesson",
                "agent_role": lesson.agent_role,
                "evidence_count": lesson.evidence_count,
            },
        ))
    return self.ingest_chunks(chunks)
```

Call from `extract_lessons.py` CLI with `--ingest-rag` flag, and optionally from auto-extract at startup.

### Files to Modify

| File | Change |
|------|--------|
| `src/ai_team/rag/pipeline.py` | Add `ingest_lessons()` method |
| `scripts/extract_lessons.py` | Add `--ingest-rag` flag |
| `src/ai_team/memory/lessons.py` | Optionally call `ingest_lessons()` from `extract_lessons()` when RAG is enabled |

---

## 11. Metrics Dashboard CLI

### Problem

No way to visualize trends without manually querying SQLite.

### Design

`scripts/show_metrics.py` — a Rich-powered CLI for querying run records and performance metrics.

```bash
# Recent runs
python scripts/show_metrics.py runs --last 20

# Success rate by backend
python scripts/show_metrics.py success-rate --group-by backend

# Code quality trend
python scripts/show_metrics.py trend --metric code_quality_score --last 30

# Cost by backend
python scripts/show_metrics.py cost --group-by backend --last 30

# Lesson effectiveness
python scripts/show_metrics.py lessons --effectiveness

# Export to JSON
python scripts/show_metrics.py runs --last 100 --format json > metrics.json
```

Renders Rich tables to the terminal. Optional `--format json` for piping.

### Files to Create

| File | Change |
|------|--------|
| `scripts/show_metrics.py` | **New.** CLI using `argparse` + `Rich` tables, reads from `LongTermStore` |

---

## 12. Implementation Tasks

### Phase 1: Foundation (Week 1) — Make the loop autonomous and measurable

| Task | Priority | Effort | Dependencies | Files |
|------|----------|--------|-------------|-------|
| **T1.1** Add `SelfImprovementSettings` to settings.py | P0 | 30m | — | `config/settings.py` |
| **T1.2** Add `run_records` table to LongTermStore schema | P0 | 1h | — | `memory/memory_config.py` |
| **T1.3** Create `RunRecord` dataclass and `RunRecordWriter` context manager | P0 | 2h | T1.2 | `memory/run_record.py` (new) |
| **T1.4** Wire RunRecordWriter into CrewAI flow `finalize_project()` | P0 | 1h | T1.3 | `flows/main_flow.py` |
| **T1.5** Wire RunRecordWriter into LangGraph `backend.run()` | P0 | 1h | T1.3 | `backends/langgraph_backend/backend.py` |
| **T1.6** Auto-extract lessons at run startup (both backends) | P0 | 1h | T1.1 | `flows/main_flow.py`, `backends/langgraph_backend/backend.py` |
| **T1.7** Lesson deduplication: add `update_pattern()` to LongTermStore | P0 | 30m | — | `memory/memory_config.py` |
| **T1.8** Lesson deduplication: upsert in `extract_lessons()` | P0 | 1h | T1.7 | `memory/lessons.py` |
| **T1.9** Add `last_seen` field to lesson schema | P0 | 30m | T1.8 | `memory/lessons.py` |
| **T1.10** Lesson TTL filtering in `load_role_lessons()` | P1 | 30m | T1.9, T1.1 | `memory/lessons.py` |
| **T1.11** Per-role lesson cap in `load_role_lessons()` | P1 | 30m | T1.1 | `memory/lessons.py` |
| **T1.12** Create `record_quality_metrics()` function | P0 | 2h | — | `memory/metrics.py` (new) |
| **T1.13** Extend `performance_metrics` schema with `run_id`, `backend` | P0 | 30m | — | `memory/memory_config.py` |
| **T1.14** Wire `record_quality_metrics()` into both backends | P0 | 1h | T1.12 | `flows/main_flow.py`, `backends/langgraph_backend/backend.py` |
| **T1.15** Unit tests for auto-extract, dedup, TTL, caps, metrics | P0 | 3h | T1.6-T1.14 | `tests/unit/test_lessons_v2.py`, `tests/unit/test_metrics.py`, `tests/unit/test_run_record.py` |

**Phase 1 total: ~16 hours**

### Phase 2: Comparison & Cost (Week 2) — Make evaluation claims credible

| Task | Priority | Effort | Dependencies | Files |
|------|----------|--------|-------------|-------|
| **T2.1** Extend `BackendRunSnapshot` with cost, quality, reliability fields | P0 | 1h | — | `models/comparison_report.py` |
| **T2.2** Update `snapshot_from_project_result()` to populate new fields | P0 | 1h | T2.1 | `models/comparison_report.py` |
| **T2.3** Update `ComparisonReport.to_markdown()` for new fields | P1 | 1h | T2.1 | `models/comparison_report.py` |
| **T2.4** Add `MultiRunComparisonReport` with stats (mean, std) | P1 | 2h | T2.1 | `models/comparison_report.py` |
| **T2.5** Add `--runs N` flag to `compare_backends.py` | P1 | 2h | T2.4 | `scripts/compare_backends.py`, `utils/backend_comparison.py` |
| **T2.6** Create `TokenTrackingCallback` for LangChain | P0 | 2h | — | `backends/langgraph_backend/token_callback.py` (new) |
| **T2.7** Attach `TokenTrackingCallback` to LangGraph model factory | P0 | 1h | T2.6 | `backends/langgraph_backend/graphs/langgraph_chat.py` |
| **T2.8** Initialize `TokenTracker` in LangGraph backend, save report | P0 | 1h | T2.6 | `backends/langgraph_backend/backend.py` |
| **T2.9** Add `BudgetSettings` to settings | P1 | 30m | — | `config/settings.py` |
| **T2.10** Implement budget enforcement in `TokenTracker.record()` | P1 | 1h | T2.9 | `config/token_tracker.py` |
| **T2.11** Add `BudgetExceededError`, catch in both backends | P1 | 1h | T2.10 | `config/token_tracker.py`, `flows/main_flow.py`, `backends/langgraph_backend/backend.py` |
| **T2.12** Create `scripts/show_runs.py` CLI | P1 | 2h | T1.2, T1.3 | `scripts/show_runs.py` (new) |
| **T2.13** Unit/integration tests for token tracking, budget, comparison | P0 | 3h | T2.6-T2.11 | `tests/unit/test_token_callback.py`, `tests/unit/test_comparison_v2.py` |

**Phase 2 total: ~18.5 hours**

### Phase 3: Refinement (Week 3-4) — Rigor and intelligence

| Task | Priority | Effort | Dependencies | Files |
|------|----------|--------|-------------|-------|
| **T3.1** Lesson effectiveness: add tracking fields to lesson schema | P1 | 1h | T1.8 | `memory/lessons.py` |
| **T3.2** Implement `record_lesson_outcomes()` | P1 | 2h | T3.1 | `memory/lessons.py` |
| **T3.3** Wire `record_lesson_outcomes()` into both backends (at finalize) | P1 | 1h | T3.2 | `flows/main_flow.py`, `backends/langgraph_backend/backend.py` |
| **T3.4** Filter ineffective lessons in `load_role_lessons()` | P1 | 30m | T3.1 | `memory/lessons.py` |
| **T3.5** Implement `detect_false_positives()` | P2 | 2h | T1.2 | `memory/lessons.py` |
| **T3.6** Create `guardrails/calibration.py` with `calibrate_guardrails()` | P2 | 3h | T3.5 | `guardrails/calibration.py` (new) |
| **T3.7** Add override loading to `role_adherence_guardrail()` | P2 | 1h | T3.6 | `guardrails/behavioral.py` |
| **T3.8** Create `scripts/calibrate_guardrails.py` with `--dry-run` | P2 | 1h | T3.6 | `scripts/calibrate_guardrails.py` (new) |
| **T3.9** Add `ingest_lessons()` to `RAGPipeline` | P2 | 1h | — | `rag/pipeline.py` |
| **T3.10** Wire RAG ingestion into `extract_lessons()` (optional flag) | P2 | 30m | T3.9 | `memory/lessons.py` |
| **T3.11** Add `--ingest-rag` to `scripts/extract_lessons.py` | P2 | 30m | T3.9 | `scripts/extract_lessons.py` |
| **T3.12** Create `scripts/show_metrics.py` dashboard CLI | P1 | 3h | T1.2, T1.12 | `scripts/show_metrics.py` (new) |
| **T3.13** Unit tests for effectiveness, calibration, RAG ingestion | P1 | 3h | T3.1-T3.11 | `tests/unit/test_effectiveness.py`, `tests/unit/test_calibration.py` |
| **T3.14** Integration test: full loop (run → capture → extract → inject → verify improvement) | P1 | 3h | all | `tests/integration/test_self_improvement_loop.py` |
| **T3.15** Update `docs/self-improvement.md` wiring checklist (mark completed items) | P2 | 30m | all | `docs/self-improvement.md` |

**Phase 3 total: ~23 hours**

---

## Summary

| Phase | Tasks | Effort | Key Outcome |
|-------|-------|--------|-------------|
| 1. Foundation | T1.1 – T1.15 | ~16h | Loop is autonomous; metrics are persisted; lessons are deduplicated |
| 2. Comparison & Cost | T2.1 – T2.13 | ~18.5h | Comparison claims are backed by data; all backends track cost |
| 3. Refinement | T3.1 – T3.15 | ~23h | Lessons self-prune; guardrails self-calibrate; full observability CLI |
| **Total** | **43 tasks** | **~57.5h** | Production-grade self-improvement mechanism |

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SQLite write contention under concurrent runs | Medium | Medium | WAL mode (default in Python 3.12+); Phase 4 future: Postgres option |
| Lesson injection degrades model performance | Low | High | TTL + cap + effectiveness tracking (Phase 1 + 3) |
| Budget enforcement aborts legitimate expensive runs | Low | Medium | Default action is `warn`, not `abort`; `abort` is opt-in |
| Guardrail calibration creates security gaps | Low | High | Auto-calibrate defaults to `false`; only `downgrade_to_warn` supported; human approval required |
| Extended comparison slows CI/CD | Medium | Low | `--runs N` is opt-in; default remains single-run |

### Metrics to Track (KPIs for the self-improvement system itself)

| KPI | Target | How Measured |
|-----|--------|-------------|
| Runs until first auto-promoted lesson | < 5 | `run_records` + `learned_patterns` timestamps |
| Lesson effectiveness rate | > 70% | `effective_count / injected_count` |
| Prompt lesson token overhead | < 500 tokens/agent | Structured log `prompt_lesson_tokens` |
| Quality score trend (30-day) | Positive slope | `performance_metrics` regression |
| False-positive guardrail rate | < 10% | `guardrail_fail_count` vs `lessons.detect_false_positives()` |
| Cost per successful run (30-day) | Decreasing | `run_records` avg where `success=1` |
