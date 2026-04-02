# Self-Improvement Mechanism: Critical Audit & Improvement Proposals

> Audit date: 2026-04-02

---

## Executive Summary

The self-improvement loop is the system's most differentiating feature — and the most unevenly implemented. **Phase 1 (Capture) and Phase 2 (Extract + Augment) are genuinely wired and producing real results.** The manager self-improvement report demonstrates the loop closing in practice. However, the mechanism has critical gaps that would block production deployment: no automatic lesson extraction, no deduplication, no guardrail calibration, no quality metrics persistence, and a comparison infrastructure too thin to justify the project's stated goal of framework evaluation.

### Maturity Scorecard

| Component | Maturity | Production-Ready? |
|-----------|----------|-------------------|
| Failure capture (post-run) | **Implemented & wired** | Yes |
| Lesson extraction (CLI) | **Implemented, manual** | No — must be automated |
| Lesson injection (prompts) | **Implemented & wired** | Yes, with caveats |
| Guardrail calibration | **Designed, not coded** | No |
| Quality metrics persistence | **Schema exists, never written** | No |
| Backend comparison | **Minimal metrics** | No — insufficient for evaluation claims |
| RAG lesson ingestion | **Designed, not coded** | No |
| Cost/token observability | **Partial** | CrewAI only; version-dependent |

---

## 1. What Works (Strengths)

### 1.1 The Capture → Extract → Inject chain is real

`record_run_failures()` fires at the end of every run (both backends, both success/error paths), writes structured failure records to SQLite, and `extract_lessons()` promotes recurring patterns into lessons that get injected into agent prompts at the next run. This is not vapor — `docs/manager_self_improvement_report.md` shows it working on a real failure (the behavioral guardrail false-positive from demo-01).

**Metric:** The loop closed in 3 runs for the demo-01 behavioral guardrail issue. This is a concrete proof point.

### 1.2 Dual-backend lesson injection

Both CrewAI (backstory append) and LangGraph (system prompt `## Lessons` section) consume lessons from the same `LongTermStore`. Adding a third backend only requires one new injection point.

### 1.3 Graceful degradation

Every lesson-related call is wrapped in `try/except` or `contextlib.suppress(Exception)`. A lesson system failure never breaks a run. This is the right design for a production system.

---

## 2. Critical Gaps

### 2.1 Lesson extraction is manual — the loop is open by default

**Problem:** `extract_lessons()` must be invoked via `scripts/extract_lessons.py` between runs. Without it, failure records accumulate but are never promoted. Run N+1 benefits from lessons **only if a human ran the CLI**. For an "autonomous" system, this is a contradiction.

**Impact:** An organization deploying this gets zero self-improvement unless they add a cron job or wrapper script. The feature looks implemented but is effectively dormant.

**Proposal:** Auto-extract at run startup.

```
# At the beginning of every run:
1. extract_lessons(threshold=2)  # promote recurring patterns
2. load_role_lessons(role)       # already wired
```

Add `auto_extract: bool = True` to configuration. Cost: one SQLite query (~ms). Risk: near zero — extraction is deterministic, no LLM calls.

**Metric to track:** `lessons_auto_promoted_count` per run, `time_to_first_lesson` (number of runs before the first lesson fires).

### 2.2 Lesson deduplication is absent

**Problem:** Each call to `extract_lessons()` appends new lesson rows without checking if the same clustering key already exists. Running the script twice doubles every lesson. Over time, agent prompts bloat with duplicate instructions.

**Impact:** Prompt bloat → increased cost, context window pressure, and potential model confusion from repetitive instructions. At scale (hundreds of runs), this is a real degradation vector.

**Proposal:** Upsert semantics — check `(pattern_type, clustering_key)` before insert. If a lesson with the same key exists, increment `occurrences` and update `last_seen`. Add a `max_lessons_per_role` cap (default: 10) with LRU eviction.

**Metric:** `prompt_lesson_tokens` per agent per run (should plateau, not grow linearly).

### 2.3 Quality metrics are never persisted

**Problem:** `performance_metrics` table exists in SQLite but has **zero writers**. The code quality guardrail computes a 0-100 score, the coverage guardrail computes pass/fail — but these scores vanish after the run. There is no way to answer "is code quality improving over time?"

**Impact:** The self-improvement loop can only learn from **failures**. It has no mechanism to learn from **gradual quality drift** (e.g., code quality dropping from 85 to 72 across runs before hitting the 70 threshold).

**Proposal:** Write quality metrics at the end of each phase:

```python
long_term_store.add_metric(
    run_id=state.run_id,
    phase="development",
    metric_name="code_quality_score",
    value=quality_result.score,
    metadata={"backend": backend, "team": team_profile}
)
```

Then expose trends: `scripts/show_metrics.py --metric code_quality_score --last 20`.

**Metrics to track:**
- `code_quality_score` (per run, per phase)
- `test_pass_rate` (per run)
- `guardrail_pass_rate` (per run, per guardrail type)
- `retry_count` (per run, per phase)

### 2.4 Guardrail calibration is unimplemented

**Problem:** The design doc describes `calibrate_guardrails()` writing `guardrail_overrides.yaml` — this doesn't exist. The behavioral guardrail's false-positive rate on the demo-01 case was 100% (the QA agent was correctly doing its job; the *input* was contaminated). The only mitigation today is a lesson telling the agent to behave differently, which is the wrong fix for a guardrail miscalibration.

**Impact:** False-positive guardrails kill runs unnecessarily. At $2-15/run (prod tier), each false kill is wasted spend. More critically, it teaches agents to *avoid* legitimate behavior to appease a miscalibrated guardrail.

**Proposal:** Implement the override mechanism with a conservative scope:

1. Track `(guardrail_name, agent_role, violation_key)` tuples with outcomes
2. When a tuple has 3+ occurrences AND the run eventually succeeded (after retry or in a later run with a lesson), mark it as `likely_false_positive`
3. Write to `guardrail_overrides.yaml`: downgrade from `fail` to `warn`
4. Require human approval for overrides (add `--approve-overrides` flag)

**Metric:** `false_positive_rate` per guardrail per role, `runs_saved_by_calibration` (runs that would have failed under old thresholds but succeeded with calibrated ones).

### 2.5 Backend comparison is not rigorous enough for the project's stated goal

**Problem:** The project README claims it's a "framework comparison platform" that "lets the data decide." But `BackendRunSnapshot` captures only: success/failure, wall-clock duration, final phase, file count. No quality scores, no token usage, no cost, no retries, no semantic output comparison, no statistical significance.

**Impact:** The comparison is a boolean (did it finish?) plus a stopwatch. This cannot support claims like "LangGraph produces better code than CrewAI" or "Claude SDK is 40% cheaper." An org evaluating frameworks based on this data would be making decisions on noise.

**Proposal:** Extend `BackendRunSnapshot` and run protocol:

```python
@dataclass
class BackendRunSnapshot:
    # Existing
    success: bool
    duration_sec: float
    current_phase: str
    generated_files_count: int

    # New: cost
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float

    # New: quality
    code_quality_score: float | None
    test_pass_count: int
    test_fail_count: int
    guardrail_pass_count: int
    guardrail_fail_count: int
    retry_count: int

    # New: per-phase timing
    phase_durations: dict[str, float]

    # New: output fingerprint for semantic comparison
    output_file_hashes: dict[str, str]
```

Add `--runs N` flag to `compare_backends.py` for statistical significance. Report mean, std, and p-value for each metric.

**Metric:** Comparison reports should include at minimum: cost per backend, quality score per backend, latency per phase per backend, retry rate per backend. Target: 5+ runs per backend per demo for meaningful comparison.

---

## 3. Risk Assessment

### 3.1 Lesson injection can degrade model performance

**Risk:** Lessons are appended to system prompts without limit. After 50 runs with diverse failures, an agent could have 20+ lessons in its prompt, consuming 2-3K tokens and potentially confusing the model with contradictory instructions.

**Mitigation:**
- Cap at `max_lessons_per_role` (default: 10)
- Add relevance scoring: only inject lessons whose `clustering_key` overlaps with the current project description (keyword or embedding similarity)
- Add a `lesson_ttl_days` (default: 90) — stale lessons expire
- Track `lesson_effectiveness`: if a lesson is present but the same failure recurs, it's ineffective — demote or rephrase

**Metric:** `lesson_hit_rate` = (runs where lesson was injected AND the corresponding failure did NOT recur) / (runs where lesson was injected).

### 3.2 SQLite is a single-point-of-failure for cross-run state

**Risk:** The `learned_patterns` table is in a single SQLite file. Concurrent runs will produce write contention. Disk corruption or accidental deletion loses all accumulated learning.

**Mitigation:**
- Short-term: WAL mode for SQLite (already default in Python 3.12+), backup on each write
- Medium-term: Optional Postgres backend for `LongTermStore` (mirrors the LangGraph checkpointing approach)
- Add `scripts/export_lessons.py` and `scripts/import_lessons.py` for portability

**Metric:** `lesson_store_size_mb`, `lesson_store_age_days`, `concurrent_write_errors_count`.

### 3.3 No feedback on lesson quality

**Risk:** The system promotes lessons based on occurrence count only. A lesson that fires 5 times but never actually prevents the failure is still injected forever.

**Mitigation:** Track lesson effectiveness:

```python
# After each run, for each injected lesson:
if failure_recurred_despite_lesson:
    lesson.ineffective_count += 1
if lesson.ineffective_count >= 3:
    lesson.status = "ineffective"  # stop injecting
```

**Metric:** `lesson_effectiveness_rate` = effective / total injected.

### 3.4 Cost of self-improvement is unmeasured

**Risk:** The lesson system adds tokens to every agent prompt, every run. For a 9-agent team with 10 lessons each, that's ~90 lesson blocks × ~50 tokens = 4,500 extra prompt tokens per run. At prod pricing (~$3/1M input tokens for Claude Sonnet), this is negligible. But with extended thinking or high-frequency runs, it compounds.

**Mitigation:** Track `self_improvement_overhead_tokens` and `self_improvement_overhead_cost_usd` per run. Include in cost reports.

---

## 4. Monitoring & Observability Gaps

### 4.1 No durable audit trail

The `TeamMonitor` is display-only (capped at 50 log lines, 20 guardrail events). When the terminal closes, everything is lost. `events.jsonl` exists but is per-project, not aggregated.

**Proposal:** Add a `RunRecord` that persists to SQLite (or a shared JSONL) after every run:

| Field | Type | Purpose |
|-------|------|---------|
| `run_id` | UUID | Unique run identifier |
| `timestamp` | ISO 8601 | When the run started |
| `backend` | str | crewai / langgraph / claude-sdk |
| `team_profile` | str | full / backend-api / prototype / ... |
| `env` | str | dev / test / prod |
| `success` | bool | Did the run complete? |
| `duration_sec` | float | Wall-clock |
| `total_cost_usd` | float | Estimated cost |
| `total_tokens` | int | Total token usage |
| `phases_completed` | list[str] | Which phases finished |
| `retry_count` | int | Total retries across phases |
| `guardrail_results` | dict | Pass/fail/warn counts per guardrail |
| `quality_scores` | dict | Code quality, test coverage, etc. |
| `lessons_injected` | int | How many lessons were active |
| `lessons_effective` | int | How many prevented a recurrence |
| `files_generated` | int | Output file count |
| `errors` | list[dict] | Structured error records |

**Metric:** This table IS the metrics. Query it for trends, dashboards, and comparison reports.

### 4.2 Token tracking is CrewAI-only and fragile

`TokenTracker` uses `crewai.hooks.register_after_llm_call_hook` which may not exist in all CrewAI versions (silently skips if missing). LangGraph has no token tracking at all — the `llm_call_count` in LangGraph state is incremented per node, not per LLM call, and tokens are not captured.

**Proposal:** Each backend's `run()` method should return token usage in `ProjectResult`. For LangGraph, wrap the `ChatOpenAI` model with a callback that captures `usage_metadata`. For Claude SDK, token usage is in the API response.

### 4.3 No alerting or budget enforcement

`TokenTracker` logs a warning when cost exceeds `AI_TEAM_MAX_COST_PER_RUN` but does not abort. For an org with a $500/month budget running 50 runs, a single runaway run could consume 10-20% of the budget.

**Proposal:** Hard budget enforcement with configurable behavior:

```
AI_TEAM_MAX_COST_PER_RUN=5.00        # USD
AI_TEAM_COST_EXCEEDED_ACTION=abort    # abort | warn | log
```

---

## 5. Organizational Adoption Considerations

### 5.1 ROI model

For an org evaluating this system, the ROI equation is:

```
ROI = (developer_hours_saved × hourly_rate) - (LLM_cost + infra_cost + adoption_cost)
         ─────────────────────────────────────────────────────────────────────────────
                                    adoption_cost + infra_cost
```

The self-improvement loop directly impacts this by:
- **Reducing LLM cost** over time (fewer retries as lessons accumulate)
- **Reducing developer intervention** (fewer manual lesson extractions, fewer false-positive investigations)
- **Increasing output quality** (lessons prevent repeat failures)

But **none of these are currently measurable** because quality metrics aren't persisted and cost tracking is partial.

### 5.2 Speed of adoption

| Barrier | Severity | Fix |
|---------|----------|-----|
| Must manually run `extract_lessons.py` | High | Auto-extract at startup |
| No dashboard for lessons/metrics trends | Medium | `scripts/show_metrics.py` or web dashboard tab |
| SQLite only, no team-shared learning | Medium | Optional Postgres + export/import |
| No documentation of what lessons look like | Low | Add examples to GETTING_STARTED.md |
| Comparison output too thin to make decisions | High | Extend BackendRunSnapshot |

### 5.3 Ease of use grading

| Aspect | Current | Target |
|--------|---------|--------|
| Self-improvement works out of the box | No (manual CLI) | Yes (auto-extract) |
| Can answer "is the system getting better?" | No (no trends) | Yes (metrics dashboard) |
| Can answer "which backend is best for my use case?" | Barely (success + time) | Yes (quality + cost + latency) |
| Can share learning across team members | No (local SQLite) | Yes (Postgres or export) |
| Can set and enforce cost budgets | Partially (warn only) | Yes (abort on exceed) |

---

## 6. Prioritized Improvement Plan

Ordered by impact-to-effort ratio, with production readiness as the filter:

| # | Improvement | Effort | Impact | Unblocks |
|---|-------------|--------|--------|----------|
| 1 | **Auto-extract lessons at run startup** | 1 hour | Critical | Makes the loop actually autonomous |
| 2 | **Lesson deduplication (upsert + cap)** | 2 hours | High | Prevents prompt bloat at scale |
| 3 | **Persist quality metrics to `performance_metrics`** | 3 hours | High | Enables trend analysis, comparison |
| 4 | **Extend `BackendRunSnapshot` with cost/quality/retries** | 4 hours | High | Makes comparison claims credible |
| 5 | **Add `RunRecord` audit trail** | 3 hours | High | Enables all dashboards and reporting |
| 6 | **Hard budget enforcement** | 1 hour | Medium | Prevents cost blowouts |
| 7 | **Lesson effectiveness tracking** | 3 hours | Medium | Prunes bad lessons, improves signal |
| 8 | **Lesson TTL + relevance filtering** | 2 hours | Medium | Prevents stale instruction accumulation |
| 9 | **LangGraph token tracking** | 2 hours | Medium | Enables cross-backend cost comparison |
| 10 | **Guardrail calibration (`guardrail_overrides.yaml`)** | 4 hours | Medium | Reduces false-positive run kills |
| 11 | **RAG lesson ingestion** | 2 hours | Low | Semantic retrieval vs keyword match |
| 12 | **Multi-run comparison with statistics** | 4 hours | Low | Statistical rigor for framework eval |

**Phase 1 (Week 1):** Items 1-3 — makes the loop production-autonomous and measurable.
**Phase 2 (Week 2):** Items 4-6 — makes comparison and cost management credible.
**Phase 3 (Week 3-4):** Items 7-12 — refinement and rigor.

---

## 7. Key Metrics Dashboard (Target State)

An org deploying this system should be able to see:

| Metric | Source | Granularity |
|--------|--------|-------------|
| **Runs per day** | RunRecord | Daily |
| **Success rate** | RunRecord | Per backend, per team profile |
| **Mean cost per run** | RunRecord + TokenTracker | Per backend, per env |
| **Code quality trend** | performance_metrics | Per run, 30-day moving avg |
| **Test pass rate trend** | performance_metrics | Per run, 30-day moving avg |
| **Retry rate** | RunRecord | Per phase, per backend |
| **Lessons active** | LongTermStore | Count, per role |
| **Lesson effectiveness** | LongTermStore | Hit rate, per lesson |
| **Guardrail false-positive rate** | LongTermStore | Per guardrail, per role |
| **Time to first successful run** | RunRecord | Per project type |
| **Cost saved by lessons** | RunRecord | (retries_before_lessons - retries_after) × cost_per_retry |

---

## Conclusion

The self-improvement mechanism is architecturally sound and partially implemented — the hard parts (failure capture, lesson extraction logic, dual-backend injection) are done. What's missing is the **automation glue** (auto-extract), **measurement infrastructure** (metrics persistence, extended comparison), and **safety rails** (dedup, TTL, budget enforcement) that separate a demo from a production system.

The gap between "this works on demo-01" and "an org can deploy this with confidence" is roughly 30 hours of focused implementation, with items 1-5 above being the critical path.
