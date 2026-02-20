"""
Tests for guardrail retry behavior: fail then succeed, max retries exceeded,
failure context in next attempt, and retry counter reset between tasks/phases.
"""

from __future__ import annotations

import pytest

from ai_team.flows.state import ProjectPhase, ProjectState
from ai_team.guardrails.security import code_safety_guardrail, crewai_code_safety_guardrail


# -----------------------------------------------------------------------------
# Guardrail fails once, retry succeeds → task completes
# -----------------------------------------------------------------------------


def test_guardrail_fails_once_retry_succeeds_task_completes() -> None:
    """When guardrail fails once and retry succeeds, the task can complete (state allows retry)."""
    # First attempt: dangerous code → fail
    bad_output = "os.system('rm -rf /')"
    passed1, result1 = crewai_code_safety_guardrail(bad_output)
    assert passed1 is False
    assert isinstance(result1, str)
    # State allows retry
    state = ProjectState(max_retries=3)
    assert state.can_retry(ProjectPhase.TESTING) is True
    state.increment_retry(ProjectPhase.TESTING)
    assert state.retry_counts.get(ProjectPhase.TESTING.value) == 1
    # Second attempt: clean code → pass (task completes)
    good_output = "def health(): return {'status': 'ok'}"
    passed2, result2 = crewai_code_safety_guardrail(good_output)
    assert passed2 is True
    assert state.can_retry(ProjectPhase.TESTING) is True
    # Task is considered complete when guardrail passes
    assert passed2 is True


# -----------------------------------------------------------------------------
# Guardrail fails max_retries times → raises (ValueError / retry limit)
# -----------------------------------------------------------------------------


def test_guardrail_fails_max_retries_times_raises() -> None:
    """When guardrail fails max_retries times, state raises (retry limit exceeded)."""
    state = ProjectState(max_retries=2)
    state.retry_counts[ProjectPhase.TESTING.value] = 2
    with pytest.raises(ValueError) as exc_info:
        state.increment_retry(ProjectPhase.TESTING)
    msg = str(exc_info.value)
    assert "Retry limit" in msg or "retry" in msg.lower()
    assert ProjectPhase.TESTING.value in msg or "testing" in msg.lower()


# -----------------------------------------------------------------------------
# Retry includes failure context in next attempt prompt
# -----------------------------------------------------------------------------


def test_retry_includes_failure_context_in_next_attempt_prompt() -> None:
    """Guardrail failure returns a message suitable for inclusion in next attempt prompt."""
    r = code_safety_guardrail("eval(user_input)")
    assert r.status == "fail"
    assert r.retry_allowed is True
    assert r.message
    assert len(r.message) > 10
    # Flow/task layer can pass r.message as context to the agent on retry
    assert "eval" in r.message.lower() or "dangerous" in r.message.lower()


# -----------------------------------------------------------------------------
# Retry counter resets between tasks (per-phase independence)
# -----------------------------------------------------------------------------


def test_retry_counter_resets_between_tasks_per_phase() -> None:
    """Retry counts are per-phase; starting a new phase does not carry over the other phase's count."""
    state = ProjectState(max_retries=3)
    state.increment_retry(ProjectPhase.TESTING)
    state.increment_retry(ProjectPhase.TESTING)
    assert state.retry_counts.get(ProjectPhase.TESTING.value) == 2
    assert state.retry_counts.get(ProjectPhase.DEVELOPMENT.value, 0) == 0
    # "New task" in another phase: development retry count is independent
    state.increment_retry(ProjectPhase.DEVELOPMENT)
    assert state.retry_counts.get(ProjectPhase.DEVELOPMENT.value) == 1
    assert state.retry_counts.get(ProjectPhase.TESTING.value) == 2
    # Can still retry testing (2 < 3)
    assert state.can_retry(ProjectPhase.TESTING) is True
    assert state.can_retry(ProjectPhase.DEVELOPMENT) is True
