# Guardrails

Guardrails keep agent output inside role, safety, and quality boundaries. The main
implementations live in `src/ai_team/guardrails/`.

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

## Testing

Guardrails are covered by focused unit tests and adversarial cases under `tests/unit/`
and `tests/guardrails/`. New guardrails should include passing, failing, and edge-case
tests, plus adversarial inputs for security-sensitive behavior.

Flow error-loop guardrails should be tested by simulating rapid consecutive failures
against a `ProjectState` instance and asserting that:
- `state.errors` length stays bounded (deduplication)
- `get_recovery_action()` returns `"escalate"` once thresholds are hit
- Backoff delays are applied on every retry action
