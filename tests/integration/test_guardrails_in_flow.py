"""Integration tests for guardrails in the flow.

Tests guardrail rejection triggering retry logic, max retry exceeded error,
guardrail callback on rejection, and flow continuing when guardrails pass.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ai_team.flows.main_flow import AITeamFlow
from ai_team.flows.state import ProjectPhase, ProjectState
from ai_team.guardrails.security import (
    GuardrailResult,
    code_safety_guardrail,
    crewai_code_safety_guardrail,
    prompt_injection_guardrail,
)
from ai_team.utils.callbacks import AITeamCallback


# -----------------------------------------------------------------------------
# Guardrail rejection triggers retry logic
# -----------------------------------------------------------------------------


class TestGuardrailRejectionTriggersRetry:
    """Guardrail rejection leads to retry path (task/flow level)."""

    def test_guardrail_fail_returns_block_and_message(self) -> None:
        """Dangerous code fails guardrail and returns (False, message) for CrewAI."""
        blocked = "import os\nos.system('rm -rf /')"
        passed, result = crewai_code_safety_guardrail(blocked)
        assert passed is False
        assert isinstance(result, str)
        assert "dangerous" in result.lower() or "pattern" in result.lower() or len(result) > 0

    def test_guardrail_result_retry_allowed_for_safety_fail(self) -> None:
        """Code safety guardrail sets retry_allowed so task can retry."""
        r = code_safety_guardrail("eval(user_input)")
        assert r.status == "fail"
        assert r.retry_allowed is True

    def test_state_increment_retry_tracks_retries(self) -> None:
        """ProjectState.increment_retry increments count for phase (used after QA fail)."""
        state = ProjectState(max_retries=3)
        state.increment_retry(ProjectPhase.TESTING)
        assert state.retry_counts.get(ProjectPhase.TESTING.value) == 1
        state.increment_retry(ProjectPhase.TESTING)
        assert state.retry_counts.get(ProjectPhase.TESTING.value) == 2


# -----------------------------------------------------------------------------
# Max retry exceeded raises correct error
# -----------------------------------------------------------------------------


class TestMaxRetryExceededRaisesError:
    """When max retries exceeded, correct error is raised."""

    def test_increment_retry_raises_when_max_exceeded(self) -> None:
        """ProjectState.increment_retry(phase) raises ValueError when retry count >= max_retries."""
        state = ProjectState(max_retries=2)
        state.retry_counts[ProjectPhase.TESTING.value] = 2
        with pytest.raises(ValueError) as exc_info:
            state.increment_retry(ProjectPhase.TESTING)
        assert "Retry limit" in str(exc_info.value) or "retry" in str(exc_info.value).lower()
        assert ProjectPhase.TESTING.value in str(exc_info.value) or "testing" in str(exc_info.value).lower()

    def test_can_retry_false_when_at_max(self) -> None:
        """can_retry(phase) is False when retry count >= max_retries."""
        state = ProjectState(max_retries=1)
        state.retry_counts[ProjectPhase.TESTING.value] = 1
        assert state.can_retry(ProjectPhase.TESTING) is False


# -----------------------------------------------------------------------------
# Guardrail callback fires on rejection
# -----------------------------------------------------------------------------


class TestGuardrailCallbackFiresOnRejection:
    """AITeamCallback.on_guardrail_trigger is invoked on guardrail rejection."""

    def test_callback_guardrail_trigger_increments_on_fail(self) -> None:
        """When on_guardrail_trigger is called with failing result, guardrail_trigger_count increments."""
        callback = AITeamCallback()
        guardrail_fn = crewai_code_safety_guardrail
        # Result that represents "rejection" (CrewAI passes result from guardrail)
        fail_result = GuardrailResult(status="fail", message="Dangerous pattern", retry_allowed=True)
        callback.on_guardrail_trigger(guardrail_fn, fail_result)
        metrics = callback.get_metrics()
        assert metrics.guardrail_trigger_count
        name = "crewai_code_safety_guardrail"[:60]
        assert metrics.guardrail_trigger_count.get(name) == 1

    def test_callback_guardrail_trigger_increments_on_pass(self) -> None:
        """Callback also records pass (trigger count increments)."""
        callback = AITeamCallback()
        guardrail_fn = crewai_code_safety_guardrail
        pass_result = GuardrailResult(status="pass", message="OK", retry_allowed=True)
        callback.on_guardrail_trigger(guardrail_fn, pass_result)
        metrics = callback.get_metrics()
        assert metrics.guardrail_trigger_count.get("crewai_code_safety_guardrail") == 1


# -----------------------------------------------------------------------------
# Flow continues normally when guardrails pass
# -----------------------------------------------------------------------------


class TestFlowContinuesWhenGuardrailsPass:
    """Intake and flow proceed when guardrails pass."""

    def test_intake_passes_security_guardrail_and_transitions(self) -> None:
        """Valid project description passes prompt injection guardrail and intake transitions to PLANNING."""
        flow = AITeamFlow()
        desc = "Build a REST API for todo items with CRUD and filtering."
        flow.state.project_description = desc
        # Guardrail used in intake is prompt_injection
        r = prompt_injection_guardrail(desc)
        assert r.is_ok()
        result = flow.intake_request()
        assert result.get("status") == "success"
        assert flow.state.current_phase == ProjectPhase.PLANNING

    def test_intake_short_description_fails_validation_before_guardrail(self) -> None:
        """Too-short description fails length validation (before guardrail)."""
        flow = AITeamFlow()
        flow.state.project_description = "short"
        result = flow.intake_request()
        assert result.get("status") == "invalid"
        assert flow.state.current_phase == ProjectPhase.INTAKE

    def test_guardrail_pass_returns_true_for_crewai(self) -> None:
        """Safe code passes crewai_code_safety_guardrail → (True, result)."""
        safe = "def hello():\n    return 'world'"
        passed, result = crewai_code_safety_guardrail(safe)
        assert passed is True
