# Guardrails

Guardrails keep agent output inside role, safety, and quality boundaries. The main
implementations live in `src/ai_team/guardrails/`.

For deep-dive post-mortems of guardrail-adjacent bugs (smoke gate, GIL starvation),
see [troubleshooting/README.md](troubleshooting/README.md). Runtime smoke verification
is documented in [SELF_IMPROVEMENT.md](SELF_IMPROVEMENT.md).

## Behavioral guardrails

Behavioral checks validate whether an agent stayed within its assigned role and task
scope. Examples:

- QA output should focus on tests and quality reports, not production source changes.
- Product Owner output should define requirements, not implementation code.
- Backend and frontend agents should avoid crossing into each other's domains unless the
  selected team profile explicitly uses the Fullstack Developer.
- Managers and architects may reference technical details while coordinating, but direct
  implementation is treated differently from delegation.

Key file: `src/ai_team/guardrails/behavioral.py`.

## Security guardrails

Security checks block or warn on risky generated content:

- dangerous execution patterns such as `eval()`, `exec()`, `os.system()`, unsafe
  `subprocess` calls, and unsafe YAML loading
- PII and secret-like strings, with redacted output in guardrail details
- prompt-injection attempts and suspicious instruction override patterns
- unsafe file paths, traversal, and sensitive filename access

Key file: `src/ai_team/guardrails/security.py`.

## Quality guardrails

Quality checks score generated code and documents for maintainability and completeness:

- Python syntax validity
- function and file size limits
- approximate cyclomatic complexity
- public function docstrings and type hints
- TODO/FIXME/HACK markers
- hardcoded credential patterns
- JSON validity and placeholder detection

Key file: `src/ai_team/guardrails/quality.py`.

## Flow error-loop guardrails

These guards live in `src/ai_team/flows/error_handling.py` and prevent infinite retry
loops when a phase fails repeatedly — a distinct failure mode from agent output quality.

### Problem

CrewAI's async event loop re-triggers listeners immediately after a router returns.
If a phase fails synchronously (Pydantic parse error, empty LLM response, Python
exception during crew construction), the error handler fires hundreds of times per
second before any LLM call is attempted. Without explicit guards this produces:

- Thousands of identical log lines and state.errors entries
- Disk write storms (state.json rewritten every iteration)
- Runs that appear "stuck" with high CPU but no useful work
- Loss of the actual stack trace (buried in noise)

### Four-layer defence (ordered cheapest → most authoritative)

| Layer | Constant | Mechanism |
|-------|----------|-----------|
| **Deduplication** | — | `_record_error_deduplicated()` only appends to `state.errors` when the message differs from the last entry. Consecutive identical errors increment the failure counter but do not grow the list. |
| **Throttled persistence** | — | `_should_persist_now()` writes `state.json` only when the error message changes. Burst of 1000 identical failures → 1 disk write. |
| **Per-phase circuit breaker** | `CIRCUIT_BREAKER_THRESHOLD = 3` | After 3 consecutive failures in one phase, `circuit_breaker_should_escalate()` returns True → immediate escalation. Resets via `reset_circuit()` on phase success. |
| **Run-level error budget** | `MAX_RUN_ERRORS = 50` | If `len(state.errors)` reaches this ceiling, `run_budget_exhausted()` returns True and `get_recovery_action()` escalates regardless of category or circuit state. Last-resort guard for novel error strings the classifier misses. |

### Backoff

All retry actions (both `RETRYABLE` and `RECOVERABLE`) apply exponential backoff via
`apply_retry_backoff(attempt)` before returning. Delays: 1 s → 2 s → 4 s → 8 s.
This prevents tight async loops even before the circuit breaker fires.

### Error classification

Errors are classified into three categories in `classify_error()`:

| Category | Recovery | Backoff | Examples |
|----------|----------|---------|---------|
| `RETRYABLE` | `retry` up to `max_retries` | Yes | Timeout, rate limit, empty LLM response, LiteLLM/OpenRouter transient errors |
| `RECOVERABLE` | `retry_with_feedback` up to `max_retries` | Yes | Pydantic validation failure, bad output format, guardrail soft-fail |
| `FATAL` | Immediate escalate | No | Model not found, OOM, recursion exhaustion, security violation |

Unknown errors default to `RECOVERABLE` (not `RETRYABLE`) so they get feedback
context on retry but still apply backoff and respect the retry cap.

### Stack traces

All four phase exception handlers (`planning_failed`, `development_failed`,
`testing_failed`, `deployment_failed`) capture `traceback.format_exc()` and store it
in `state.metadata["last_crew_error"]["stack_trace"]`. The structured error log entry
(`StructuredErrorLog.stack_trace`) also carries it. Inspect a failed run with:

```bash
python3 -c "
import json
s = json.load(open('output/runs/<run-id>/state.json'))
print(s['metadata'].get('last_crew_error', {}).get('stack_trace', 'no trace'))
"
```

### Tuning constants

All constants are at the top of `error_handling.py`:

```python
RETRY_BACKOFF_DELAYS = [1, 2, 4, 8]   # seconds; extend to add more attempts
CIRCUIT_BREAKER_THRESHOLD = 3          # consecutive failures before escalation
MAX_CONSECUTIVE_FAILURES_CAP = 10      # hard cap on counter (prevents integer overflow)
MAX_RUN_ERRORS = 50                    # total errors across all phases before hard stop
```

## LangGraph backend operational guardrails

The CrewAI flow guards above protect the CrewAI backend. The LangGraph backend has its
own set of **operational** guardrails — distinct from content guardrails — that bound
*how long* and *how much money* a run can spend, and recover from common model
non-compliance (e.g. a model emitting code as prose instead of calling `file_writer`).

These exist because the failure modes are real: a hung LLM/tool call can block a run
indefinitely, a crash-and-retry cycle can burn many paid LLM calls, and a model that
returns test code as markdown leaves the workspace empty so `pytest` collects 0 items
and the run fails terminally with nothing to show.

### Wall-clock watchdog (CLI)

`scripts/run_demo.py` has no internal watchdog of its own, so a hung call could
previously block forever. The `--timeout` flag arms a `SIGALRM` watchdog that aborts a
hung run with a clear message and exit code `124`.

```bash
# Default 900s budget; 0 disables.
uv run python scripts/run_demo.py demos/02_todo_app --backend langgraph --timeout 600
```

`SIGALRM` is Unix-only and fires on the main thread (where the flow runs synchronously);
on platforms without it the run is untimed.

### Recoverable testing-phase routing

`route_after_testing` (`backends/langgraph_backend/graphs/routing.py`) treats a
*testing-phase* error — e.g. the QA agent emitting prose instead of a `file_writer`
tool-call, or a malformed tool-call that crashes the subgraph — as **retryable**: route
back to development up to `max_retries` (default 3), then escalate to a human. Errors
from *other* phases stay terminal (a hard fault re-running QA cannot fix).

This relies on a custom `errors` reducer, `reset_or_extend_errors`
(`graphs/state.py`): an empty `"errors": []` update **resets** the accumulated list (the
recovery signal a clean retry returns), while a non-empty update appends. The previous
`operator.add` reducer made `"errors": []` a no-op, so stale errors persisted and forced
terminal routing even after recovery. `retry_development` clears errors on each attempt.

The quality gate (`_run_real_quality_gate`) also surfaces pytest exit code 5 ("no tests
collected") as a distinct `no_tests_collected` signal with actionable reason text, so a
retry can tell the developer/QA "no tests were written" rather than treating it like an
ordinary test failure.

### Prose-as-files salvage

When a model (notably deepseek via OpenRouter) writes code as markdown prose instead of
calling `file_writer`, `_extract_and_write_code_blocks`
(`graphs/subgraph_runners.py`) parses fenced blocks with adjacent filenames and writes
them to the workspace. Three regexes cover the common shapes, including
markdown-header-named blocks (e.g. ``### `test_calc.py` `` followed by a fence). The
testing node salvages test files this way on both the normal and exception paths, then
runs the gate instead of failing outright.

> **Security:** extraction validates each filename **before** writing — it strips at most
> one leading `./`, then rejects absolute paths, `..` traversal segments, and dotfiles.
> Do **not** reintroduce `lstrip("./")` here: it strips arbitrary leading dot/slash
> characters and turns `../escape.py` into `escape.py`, defeating the traversal check.
> Covered by adversarial tests in `tests/unit/backends/langgraph_backend/test_code_extraction.py`.

### Spend ceiling and recursion limit

Two loop-spend guards bound a runaway crash/retry cycle:

| Guard | Default | Override | Mechanism |
|-------|---------|----------|-----------|
| **Run spend ceiling** | `$5.00` | `AI_TEAM_RUN_BUDGET_USD` (`0` disables) | `graphs/spend_guard.py` accumulates real per-call `cost` from the OpenRouter response (read in the `langgraph_chat` httpx hook). Crossing the ceiling raises `BudgetExceededError`. |
| **Graph recursion limit** | `50` | `AI_TEAM_LANGGRAPH_RECURSION_LIMIT` | Explicit `recursion_limit` on graph `invoke`/`stream`, instead of the LangGraph default of 25. Bounds total supersteps deterministically. |

`BudgetExceededError` subclasses **`BaseException`**, not `Exception`, on purpose. The
phase subgraph nodes wrap `sub.invoke` in `except Exception` and convert failures into
*retryable* error dicts — but a budget abort must **not** be retried (retrying is exactly
what we're stopping). Subclassing `BaseException` makes it bypass those handlers and
propagate straight out, like `KeyboardInterrupt`. It is caught explicitly at the backend
`run`/`stream` boundary and turned into a clean `success=False` result (exit 1), never an
unhandled traceback or a silent "complete".

Budget is **per run**: `reset_spend_guard()` is called at the start of `run()` and
`stream()`; `0` keeps tracking on (for reporting) but lifts the ceiling.

```bash
# Abort if a run's cumulative OpenRouter spend exceeds $3.
AI_TEAM_RUN_BUDGET_USD=3.00 uv run python scripts/run_demo.py demos/02_todo_app --backend langgraph
```

### Tuning constants

| Constant | File | Meaning |
|----------|------|---------|
| `DEFAULT_TIMEOUT_S = 900` | `scripts/run_demo.py` | Default `--timeout` wall-clock budget (s). |
| `max_retries = 3` | `backends/langgraph_backend/backend.py` | Phase retry cap (dev ↔ testing). |
| `MAX_SUBGRAPH_GUARDRAIL_RETRIES = 3` | `graphs/langgraph_guardrail_nodes.py` | Per-subgraph guardrail retry cap. |
| `DEFAULT_RECURSION_LIMIT = 50` | `backends/langgraph_backend/backend.py` | Graph superstep cap. |
| `DEFAULT_BUDGET_USD = 5.0` | `graphs/spend_guard.py` | Default per-run spend ceiling (USD). |

## Testing

Guardrails are covered by focused unit tests and adversarial cases under `tests/unit/`
and `tests/guardrails/`. New guardrails should include passing, failing, and edge-case
tests, plus adversarial inputs for security-sensitive behavior.

LangGraph operational guardrails live under
`tests/unit/backends/langgraph_backend/` — see `test_routing.py` (testing-error
recovery), `test_state_schema.py` (the `errors` reducer reset), `test_code_extraction.py`
(salvage + path-traversal adversarial cases), and `test_spend_guard.py` (spend ceiling
and the non-retryable `BaseException` semantics).

Flow error-loop guardrails should be tested by simulating rapid consecutive failures
against a `ProjectState` instance and asserting that:
- `state.errors` length stays bounded (deduplication)
- `get_recovery_action()` returns `"escalate"` once thresholds are hit
- Backoff delays are applied on every retry action
