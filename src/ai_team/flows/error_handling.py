"""
Flow error recovery for AITeamFlow.

Provides error classification (Retryable, Recoverable, Fatal), recovery strategies,
circuit breaker per phase, state preservation (save on error, resume, rollback),
and structured error reporting with metrics.

## Loop-prevention guardrails (layered defence)

Four independent guards prevent infinite error loops, ordered from cheapest to invoke:

1. **Run-level error budget** (``MAX_RUN_ERRORS = 50``): if total errors across the
   entire run reaches this ceiling, the next ``_handle_phase_error`` call immediately
   escalates regardless of category or circuit-breaker state. Catches novel error
   strings that bypass the per-phase circuit breaker.

2. **Per-phase circuit breaker** (``CIRCUIT_BREAKER_THRESHOLD = 3``): if the same
   phase fails consecutively ≥3 times, escalate. Resets on phase success via
   ``reset_circuit()``.

3. **Exponential backoff on every retry** (``RETRY_BACKOFF_DELAYS = [1, 2, 4, 8]``):
   applied to both RETRYABLE and RECOVERABLE actions via ``apply_retry_backoff()``.
   Prevents tight async loops even when the circuit breaker hasn't fired yet.

4. **Deduplicated error recording**: if the last recorded error in ``state.errors``
   has the same message as the current one, it is counted but not appended again.
   Keeps the error list readable and prevents state.json from ballooning during bursts.

Additionally, ``persist_state_on_error`` is throttled: it only writes to disk when the
error is the first of a burst (i.e., the last persisted error had a different message).
"""

from __future__ import annotations

import contextlib
import json
import time
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import structlog
from ai_team.flows.state import ProjectPhase, ProjectState
from pydantic import BaseModel, Field

logger = structlog.get_logger()

# Backoff delays in seconds for retryable errors: 1s, 2s, 4s, 8s
RETRY_BACKOFF_DELAYS = [1, 2, 4, 8]
CIRCUIT_BREAKER_THRESHOLD = 3
# Cap consecutive failures so a bad state file or loop cannot inflate indefinitely
MAX_CONSECUTIVE_FAILURES_CAP = 10
# Run-level hard ceiling: if total errors across all phases reaches this, escalate immediately.
# Acts as a last-resort guard against novel error strings that slip past the circuit breaker.
MAX_RUN_ERRORS = 50
# Metadata key used to throttle state persistence during error bursts
_LAST_PERSISTED_ERROR_KEY = "_last_persisted_error_msg"


# -----------------------------------------------------------------------------
# Error classification
# -----------------------------------------------------------------------------


class ErrorCategory(str, Enum):
    """Classification of flow/crew errors for recovery strategy."""

    RETRYABLE = "retryable"  # LLM timeout, rate limit, temporary Ollama failure
    RECOVERABLE = "recoverable"  # Invalid output format, guardrail soft failure
    FATAL = "fatal"  # Model not found, OOM, critical security violation


# Substrings that indicate each category (case-insensitive)
RETRYABLE_INDICATORS = [
    "timeout",
    "timed out",
    "rate limit",
    "rate_limit",
    "connection refused",
    "connection reset",
    "temporary",
    "503",
    "429",
    "try again",
    "retry",
    "ollama",
    "connection error",
    # LiteLLM / OpenRouter transient provider errors
    "litellm",
    "apierror",
    "openrouterexception",
    "unable to get json response",
    # CrewAI agent_utils: LLM returned None/empty — transient provider issue
    "invalid response from llm call",
    "none or empty",
    "wall-clock",
    "exceeded",
]
FATAL_INDICATORS = [
    "model not found",
    "out of memory",
    "oom",
    "memory error",
    "critical security",
    "security violation",
    "fatal",
    "cannot load",
    # Do not retry planning/crews on Python recursion exhaustion (often worsens or crashes native libs).
    "maximum recursion depth",
    "recursionerror",
    "recursion depth",
]
RECOVERABLE_INDICATORS = [
    "invalid output",
    "invalid format",
    "parse error",
    "validation error",
    "guardrail",
    "json",
    "schema",
    "expected",
]


def classify_error(error: dict[str, Any]) -> ErrorCategory:
    """
    Classify an error dict into Retryable, Recoverable, or Fatal.

    Uses heuristics on the error message. Fatal is checked first, then
    Retryable, then Recoverable as default for unknown/format issues.
    """
    msg = (error.get("error") or error.get("message") or str(error)).lower()
    for indicator in FATAL_INDICATORS:
        if indicator in msg:
            return ErrorCategory.FATAL
    for indicator in RETRYABLE_INDICATORS:
        if indicator in msg:
            return ErrorCategory.RETRYABLE
    for indicator in RECOVERABLE_INDICATORS:
        if indicator in msg:
            return ErrorCategory.RECOVERABLE
    # Default: treat unknown as recoverable (e.g. generic exception)
    return ErrorCategory.RECOVERABLE


# -----------------------------------------------------------------------------
# Structured error log and reporting
# -----------------------------------------------------------------------------


class StructuredErrorLog(BaseModel):
    """Structured error log entry: phase, agent, tool, error type, stack trace."""

    phase: str = Field(..., description="Phase when error occurred")
    agent: str | None = Field(default=None, description="Agent involved if known")
    tool: str | None = Field(default=None, description="Tool involved if known")
    error_type: str = Field(..., description="Error category or code")
    message: str = Field(..., description="Human-readable message")
    stack_trace: str | None = Field(default=None, description="Stack trace if available")
    timestamp: str = Field(default="", description="ISO timestamp")


def record_structured_error(
    phase: ProjectPhase,
    error_type: str,
    message: str,
    agent: str | None = None,
    tool: str | None = None,
    stack_trace: str | None = None,
) -> StructuredErrorLog:
    """Build and return a structured error log entry; log it via structlog."""

    entry = StructuredErrorLog(
        phase=phase.value,
        agent=agent,
        tool=tool,
        error_type=error_type,
        message=message,
        stack_trace=stack_trace,
        timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    logger.error(
        "flow_error",
        phase=entry.phase,
        error_type=entry.error_type,
        message=entry.message[:200] if len(entry.message) > 200 else entry.message,
        agent=entry.agent,
        tool=entry.tool,
    )
    return entry


def build_error_summary_report(state: ProjectState) -> str:
    """Produce a human-readable summary of errors for review."""
    lines = [
        f"Project: {state.project_id}",
        f"Phase: {state.current_phase.value}",
        f"Total errors: {len(state.errors)}",
        "",
    ]
    for i, err in enumerate(state.errors, 1):
        lines.append(
            f"  {i}. [{err.phase.value}] {err.error_type}: {err.message[:200]}"
            + ("..." if len(err.message) > 200 else "")
        )
    if state.retry_counts:
        lines.append("")
        lines.append("Retry counts by phase:")
        for phase_key, count in state.retry_counts.items():
            lines.append(f"  {phase_key}: {count}")
    return "\n".join(lines)


def get_error_metrics(state: ProjectState) -> dict[str, Any]:
    """Return metrics: error rate per phase, retry count distribution."""
    total_by_phase: dict[str, int] = {}
    for err in state.errors:
        key = err.phase.value
        total_by_phase[key] = total_by_phase.get(key, 0) + 1
    return {
        "error_count_by_phase": total_by_phase,
        "retry_count_distribution": dict(state.retry_counts),
        "total_errors": len(state.errors),
    }


# -----------------------------------------------------------------------------
# Circuit breaker
# -----------------------------------------------------------------------------


def _consecutive_failures_key(phase: ProjectPhase) -> str:
    return f"consecutive_failures_{phase.value}"


def get_consecutive_failures(state: ProjectState, phase: ProjectPhase) -> int:
    """Return number of consecutive failures for the given phase (stored in metadata)."""
    key = _consecutive_failures_key(phase)
    return int(state.metadata.get(key, 0))


def record_failure(state: ProjectState, phase: ProjectPhase) -> int:
    """Increment consecutive failure count for phase (capped); return new count."""
    key = _consecutive_failures_key(phase)
    current = int(state.metadata.get(key, 0))
    new_count = min(current + 1, MAX_CONSECUTIVE_FAILURES_CAP)
    state.metadata[key] = new_count
    return new_count


def reset_circuit(state: ProjectState, phase: ProjectPhase) -> None:
    """Reset consecutive failure count for phase (call on success)."""
    key = _consecutive_failures_key(phase)
    state.metadata[key] = 0


def circuit_breaker_should_escalate(state: ProjectState, phase: ProjectPhase) -> bool:
    """Return True if 3+ consecutive failures in same phase → escalate to human."""
    return get_consecutive_failures(state, phase) >= CIRCUIT_BREAKER_THRESHOLD


def run_budget_exhausted(state: ProjectState) -> bool:
    """Return True if total errors across all phases hit MAX_RUN_ERRORS.

    This is the run-level last-resort guard. It fires before per-phase circuit
    breaker logic so novel error strings cannot loop indefinitely even if the
    classifier misses them.
    """
    return len(state.errors) >= MAX_RUN_ERRORS


def _record_error_deduplicated(
    state: ProjectState,
    phase: ProjectPhase,
    error_type: str,
    msg: str,
    *,
    recoverable: bool = True,
) -> bool:
    """Append error to state.errors only if it differs from the last recorded message.

    Returns True if appended (novel error), False if suppressed (duplicate burst).
    Duplicate errors are still counted via the consecutive_failures counter; they just
    don't bloat the errors list with thousands of identical entries.
    """
    if state.errors and state.errors[-1].message == msg:
        return False
    state.add_error(phase, error_type, msg, recoverable=recoverable)
    return True


# -----------------------------------------------------------------------------
# State preservation
# -----------------------------------------------------------------------------


def persist_state_on_error(state: ProjectState, error_info: dict[str, Any] | None = None) -> Path:
    """
    Save ProjectState to ``output/runs/<project_id>/state.json`` on error.
    Optionally merge error_info into state.metadata for resume context.
    Returns path to written file.
    """
    from ai_team.core.results import ResultsBundle, scorecard_from_project_state

    if error_info:
        state.metadata["last_error"] = error_info
    b = ResultsBundle(state.project_id)
    b.init_dirs()
    path = b.write_state(state.model_dump(mode="json"))
    with contextlib.suppress(Exception):
        b.write_scorecard(
            scorecard_from_project_state(
                state.project_id,
                state,
                status="error",
                backend="crewai",
            )
        )
    logger.info("state_persisted_on_error", path=str(path))
    return path


def load_state_from_file(path: Path) -> ProjectState:
    """Load ProjectState from a JSON file for resume. Resets consecutive_failures_* so a new run does not inherit old counts."""
    data = json.loads(path.read_text(encoding="utf-8"))
    state = ProjectState.model_validate(data)
    meta = state.metadata
    for phase in ProjectPhase:
        key = _consecutive_failures_key(phase)
        if key in meta:
            meta[key] = 0
    return state


def rollback_last_phase(state: ProjectState) -> ProjectPhase | None:
    """
    Undo last phase transition: revert current_phase and remove last transition from history.
    Returns the phase we rolled back to, or None if no valid rollback.
    """
    if not state.phase_history:
        return None
    last = state.phase_history.pop()
    state.current_phase = last.from_phase
    return last.from_phase


# -----------------------------------------------------------------------------
# Recovery strategy
# -----------------------------------------------------------------------------


def get_backoff_delay(attempt: int) -> float:
    """Return delay in seconds for attempt (0-based). Caps at last element of RETRY_BACKOFF_DELAYS."""
    if attempt < 0:
        return float(RETRY_BACKOFF_DELAYS[0])
    if attempt >= len(RETRY_BACKOFF_DELAYS):
        return float(RETRY_BACKOFF_DELAYS[-1])
    return float(RETRY_BACKOFF_DELAYS[attempt])


def apply_retry_backoff(attempt: int) -> None:
    """Sleep for exponential backoff for the given attempt (0-based)."""
    delay = get_backoff_delay(attempt)
    logger.info("retry_backoff", attempt=attempt, delay_seconds=delay)
    time.sleep(delay)


RecoveryAction = str  # "retry" | "retry_with_feedback" | "escalate"


def _should_persist_now(state: ProjectState, msg: str) -> bool:
    """Return True only when this error message differs from the last persisted one.

    Prevents a disk-write storm during tight error loops where the same exception
    fires hundreds of times per second.
    """
    last = state.metadata.get(_LAST_PERSISTED_ERROR_KEY, "")
    if last == msg:
        return False
    state.metadata[_LAST_PERSISTED_ERROR_KEY] = msg
    return True


def get_recovery_action(
    category: ErrorCategory,
    state: ProjectState,
    phase: ProjectPhase,
    max_retries: int | None = None,
) -> tuple[RecoveryAction, dict[str, Any]]:
    """
    Determine recovery action and payload.

    Returns (action, payload). action is "retry" | "retry_with_feedback" | "escalate".
    payload may include backoff_attempt, feedback_message, etc.
    """
    max_retries = max_retries or state.max_retries
    payload: dict[str, Any] = {}

    # Guard 1: run-level error budget (catches novel error strings before circuit breaker)
    if run_budget_exhausted(state):
        logger.error(
            "run_error_budget_exhausted",
            total_errors=len(state.errors),
            max=MAX_RUN_ERRORS,
            phase=phase.value,
        )
        return "escalate", {
            "reason": "run_error_budget_exhausted",
            "total_errors": len(state.errors),
        }

    # Guard 2: per-phase circuit breaker
    if circuit_breaker_should_escalate(state, phase):
        return "escalate", {
            "reason": "circuit_breaker",
            "consecutive_failures": get_consecutive_failures(state, phase),
        }

    if category == ErrorCategory.FATAL:
        return "escalate", {"reason": "fatal_error"}

    if category == ErrorCategory.RETRYABLE:
        # Use consecutive failures as the "attempt" for backoff
        attempt = get_consecutive_failures(state, phase)
        if attempt >= max_retries:
            return "escalate", {"reason": "max_retries_exceeded", "attempts": attempt}
        payload["backoff_attempt"] = attempt
        return "retry", payload

    if category == ErrorCategory.RECOVERABLE:
        # Retry with feedback — honour max_retries cap and apply backoff to prevent tight loops.
        # Recoverable errors (Pydantic validation, bad output format) can fail synchronously
        # at Python speed; backoff is essential to avoid spinning the async event loop.
        attempt = get_consecutive_failures(state, phase)
        if attempt >= max_retries:
            return "escalate", {"reason": "max_retries_exceeded", "attempts": attempt}
        payload["backoff_attempt"] = attempt
        return "retry_with_feedback", {
            "reason": "recoverable",
            "feedback": "Please fix the reported issue and try again.",
            **payload,
        }

    return "escalate", {"reason": "unknown"}


# -----------------------------------------------------------------------------
# Error handler entry points (for AITeamFlow)
# -----------------------------------------------------------------------------


def handle_planning_error(
    state: ProjectState,
    error: dict[str, Any],
    persist_fn: Any | None = None,
) -> dict[str, Any]:
    """
    Handle planning crew execution failure: classify, record, persist, decide action.
    Returns dict with status, action, summary, path, etc. for flow routing.
    """
    phase = ProjectPhase.PLANNING
    return _handle_phase_error(state, phase, "planning", error, persist_fn)


def handle_development_error(
    state: ProjectState,
    error: dict[str, Any],
    persist_fn: Any | None = None,
) -> dict[str, Any]:
    """Handle development (code generation) failure."""
    phase = ProjectPhase.DEVELOPMENT
    return _handle_phase_error(state, phase, "development", error, persist_fn)


def handle_testing_error(
    state: ProjectState,
    error: dict[str, Any],
    persist_fn: Any | None = None,
) -> dict[str, Any]:
    """Handle testing crew execution failure."""
    phase = ProjectPhase.TESTING
    return _handle_phase_error(state, phase, "testing", error, persist_fn)


def handle_deployment_error(
    state: ProjectState,
    error: dict[str, Any],
    persist_fn: Any | None = None,
) -> dict[str, Any]:
    """Handle deployment/packaging failure."""
    phase = ProjectPhase.DEPLOYMENT
    return _handle_phase_error(state, phase, "deployment", error, persist_fn)


def _handle_phase_error(
    state: ProjectState,
    phase: ProjectPhase,
    phase_name: str,
    error: dict[str, Any],
    persist_fn: Any | None = None,
) -> dict[str, Any]:
    """
    Shared logic: classify error, record in state, persist, circuit breaker, recovery action.

    Loop-prevention measures applied here (see module docstring for full design):
    - Deduplicated error recording: identical consecutive messages not re-appended.
    - Throttled persistence: state.json only written when error message changes.
    - Run-level budget and per-phase circuit breaker checked in get_recovery_action().
    """
    msg = error.get("error") or error.get("message") or str(error)

    # Deduplicated recording — always increment failure counter but only append novel errors
    is_novel = _record_error_deduplicated(
        state, phase, f"{phase_name}_error", msg, recoverable=True
    )

    category = classify_error(error)
    record_failure(state, phase)

    # Only log + build structured entry for novel errors to avoid log spam
    if is_novel:
        structured = record_structured_error(
            phase=phase,
            error_type=category.value,
            message=msg,
            stack_trace=error.get("stack_trace"),
        )
    else:
        # Build entry without logging (suppress repeat spam)
        structured = StructuredErrorLog(
            phase=phase.value,
            error_type=category.value,
            message=msg,
            stack_trace=error.get("stack_trace"),
            timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )

    # Throttled persistence — only write disk when error message changes
    should_persist = _should_persist_now(state, msg)
    if should_persist:
        if persist_fn is not None:
            try:
                persist_fn(state)
            except Exception as e:
                logger.warning("state_persistence_failed", error=str(e))
        else:
            try:
                persist_state_on_error(
                    state, {"phase": phase_name, "error": msg, "category": category.value}
                )
            except Exception as e:
                logger.warning("state_persistence_failed", error=str(e))

    action, payload = get_recovery_action(category, state, phase)
    summary = build_error_summary_report(state)
    metrics = get_error_metrics(state)

    result: dict[str, Any] = {
        "status": "error",
        "phase": phase_name,
        "action": action,
        "category": category.value,
        "errors": [e.model_dump() for e in state.errors],
        "summary_report": summary,
        "metrics": metrics,
        "structured_log": structured.model_dump(),
    }
    result.update(payload)

    if action in ("retry", "retry_with_feedback") and "backoff_attempt" in payload:
        apply_retry_backoff(payload["backoff_attempt"])

    # Transition to ERROR only when we escalate; otherwise flow will retry
    if action == "escalate":
        state.add_phase_transition(phase, ProjectPhase.ERROR, "Error escalation")

    return result
