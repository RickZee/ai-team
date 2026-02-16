"""
Flow error recovery for AITeamFlow.

Provides error classification (Retryable, Recoverable, Fatal), recovery strategies,
circuit breaker per phase, state preservation (save on error, resume, rollback),
and structured error reporting with metrics.
"""

from __future__ import annotations

import json
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog
from pydantic import BaseModel, Field

from ai_team.config.settings import get_settings
from ai_team.flows.state import ProjectPhase, ProjectState

logger = structlog.get_logger()

# Backoff delays in seconds for retryable errors: 1s, 2s, 4s, 8s
RETRY_BACKOFF_DELAYS = [1, 2, 4, 8]
CIRCUIT_BREAKER_THRESHOLD = 3


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
    "not found",
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


def classify_error(error: Dict[str, Any]) -> ErrorCategory:
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
    agent: Optional[str] = Field(default=None, description="Agent involved if known")
    tool: Optional[str] = Field(default=None, description="Tool involved if known")
    error_type: str = Field(..., description="Error category or code")
    message: str = Field(..., description="Human-readable message")
    stack_trace: Optional[str] = Field(default=None, description="Stack trace if available")
    timestamp: str = Field(default="", description="ISO timestamp")


def record_structured_error(
    phase: ProjectPhase,
    error_type: str,
    message: str,
    agent: Optional[str] = None,
    tool: Optional[str] = None,
    stack_trace: Optional[str] = None,
) -> StructuredErrorLog:
    """Build and return a structured error log entry; log it via structlog."""
    from datetime import datetime

    entry = StructuredErrorLog(
        phase=phase.value,
        agent=agent,
        tool=tool,
        error_type=error_type,
        message=message,
        stack_trace=stack_trace,
        timestamp=datetime.utcnow().isoformat() + "Z",
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


def get_error_metrics(state: ProjectState) -> Dict[str, Any]:
    """Return metrics: error rate per phase, retry count distribution."""
    total_by_phase: Dict[str, int] = {}
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
    """Increment consecutive failure count for phase; return new count."""
    key = _consecutive_failures_key(phase)
    current = int(state.metadata.get(key, 0))
    new_count = current + 1
    state.metadata[key] = new_count
    return new_count


def reset_circuit(state: ProjectState, phase: ProjectPhase) -> None:
    """Reset consecutive failure count for phase (call on success)."""
    key = _consecutive_failures_key(phase)
    state.metadata[key] = 0


def circuit_breaker_should_escalate(state: ProjectState, phase: ProjectPhase) -> bool:
    """Return True if 3+ consecutive failures in same phase → escalate to human."""
    return get_consecutive_failures(state, phase) >= CIRCUIT_BREAKER_THRESHOLD


# -----------------------------------------------------------------------------
# State preservation
# -----------------------------------------------------------------------------


def persist_state_on_error(state: ProjectState, error_info: Optional[Dict[str, Any]] = None) -> Path:
    """
    Save ProjectState to JSON in output_dir on error.
    Optionally merge error_info into state.metadata for resume context.
    Returns path to written file.
    """
    if error_info:
        state.metadata["last_error"] = error_info
    settings = get_settings()
    out_dir = Path(settings.project.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{state.project_id}_state.json"
    data = state.model_dump(mode="json")
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("state_persisted_on_error", path=str(path))
    return path


def load_state_from_file(path: Path) -> ProjectState:
    """Load ProjectState from a JSON file for resume."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProjectState.model_validate(data)


def rollback_last_phase(state: ProjectState) -> Optional[ProjectPhase]:
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


def get_recovery_action(
    category: ErrorCategory,
    state: ProjectState,
    phase: ProjectPhase,
    max_retries: Optional[int] = None,
) -> Tuple[RecoveryAction, Dict[str, Any]]:
    """
    Determine recovery action and payload.

    Returns (action, payload). action is "retry" | "retry_with_feedback" | "escalate".
    payload may include backoff_attempt, feedback_message, etc.
    """
    max_retries = max_retries or state.max_retries
    payload: Dict[str, Any] = {}

    if circuit_breaker_should_escalate(state, phase):
        return "escalate", {"reason": "circuit_breaker", "consecutive_failures": get_consecutive_failures(state, phase)}

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
        # Retry with feedback (caller can inject feedback into next prompt)
        return "retry_with_feedback", {"reason": "recoverable", "feedback": "Please fix the reported issue and try again."}

    return "escalate", {"reason": "unknown"}


# -----------------------------------------------------------------------------
# Error handler entry points (for AITeamFlow)
# -----------------------------------------------------------------------------


def handle_planning_error(
    state: ProjectState,
    error: Dict[str, Any],
    persist_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Handle planning crew execution failure: classify, record, persist, decide action.
    Returns dict with status, action, summary, path, etc. for flow routing.
    """
    phase = ProjectPhase.PLANNING
    return _handle_phase_error(state, phase, "planning", error, persist_fn)


def handle_development_error(
    state: ProjectState,
    error: Dict[str, Any],
    persist_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """Handle development (code generation) failure."""
    phase = ProjectPhase.DEVELOPMENT
    return _handle_phase_error(state, phase, "development", error, persist_fn)


def handle_testing_error(
    state: ProjectState,
    error: Dict[str, Any],
    persist_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """Handle testing crew execution failure."""
    phase = ProjectPhase.TESTING
    return _handle_phase_error(state, phase, "testing", error, persist_fn)


def handle_deployment_error(
    state: ProjectState,
    error: Dict[str, Any],
    persist_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """Handle deployment/packaging failure."""
    phase = ProjectPhase.DEPLOYMENT
    return _handle_phase_error(state, phase, "deployment", error, persist_fn)


def _handle_phase_error(
    state: ProjectState,
    phase: ProjectPhase,
    phase_name: str,
    error: Dict[str, Any],
    persist_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Shared logic: classify error, record in state, persist, circuit breaker, recovery action.
    """
    msg = error.get("error") or error.get("message") or str(error)
    state.add_error(phase, f"{phase_name}_error", msg, recoverable=True)

    category = classify_error(error)
    record_failure(state, phase)

    structured = record_structured_error(
        phase=phase,
        error_type=category.value,
        message=msg,
        stack_trace=error.get("stack_trace"),
    )

    # Persist state on every error
    if persist_fn is not None:
        try:
            persist_fn(state)
        except Exception as e:
            logger.warning("state_persistence_failed", error=str(e))
    else:
        try:
            persist_state_on_error(state, {"phase": phase_name, "error": msg, "category": category.value})
        except Exception as e:
            logger.warning("state_persistence_failed", error=str(e))

    action, payload = get_recovery_action(category, state, phase)
    summary = build_error_summary_report(state)
    metrics = get_error_metrics(state)

    result: Dict[str, Any] = {
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

    if action == "retry" and "backoff_attempt" in payload:
        apply_retry_backoff(payload["backoff_attempt"])

    # Transition to ERROR only when we escalate; otherwise flow will retry
    if action == "escalate":
        state.add_phase_transition(phase, ProjectPhase.ERROR, "Error escalation")

    return result
