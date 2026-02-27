"""Unit tests for flow error handling: classification, recovery, circuit breaker, state."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_team.flows.error_handling import (
    CIRCUIT_BREAKER_THRESHOLD,
    ErrorCategory,
    RETRY_BACKOFF_DELAYS,
    apply_retry_backoff,
    build_error_summary_report,
    circuit_breaker_should_escalate,
    classify_error,
    get_backoff_delay,
    get_consecutive_failures,
    get_error_metrics,
    get_recovery_action,
    handle_deployment_error,
    handle_development_error,
    handle_planning_error,
    handle_testing_error,
    load_state_from_file,
    persist_state_on_error,
    record_failure,
    record_structured_error,
    reset_circuit,
    rollback_last_phase,
)
from ai_team.flows.state import ProjectPhase, ProjectState


# -----------------------------------------------------------------------------
# Error classification
# -----------------------------------------------------------------------------


class TestClassifyError:
    """Tests for classify_error."""

    def test_retryable_timeout(self) -> None:
        assert classify_error({"error": "Request timed out"}) == ErrorCategory.RETRYABLE

    def test_retryable_rate_limit(self) -> None:
        assert classify_error({"error": "Rate limit exceeded"}) == ErrorCategory.RETRYABLE

    def test_retryable_connection_refused(self) -> None:
        assert classify_error({"error": "Connection refused"}) == ErrorCategory.RETRYABLE

    def test_retryable_429(self) -> None:
        assert classify_error({"error": "HTTP 429 Too Many Requests"}) == ErrorCategory.RETRYABLE

    def test_fatal_model_not_found(self) -> None:
        assert classify_error({"error": "model not found"}) == ErrorCategory.FATAL

    def test_fatal_out_of_memory(self) -> None:
        assert classify_error({"error": "Out of memory"}) == ErrorCategory.FATAL

    def test_fatal_critical_security(self) -> None:
        assert classify_error({"error": "Critical security violation"}) == ErrorCategory.FATAL

    def test_recoverable_invalid_output(self) -> None:
        assert classify_error({"error": "Invalid output format"}) == ErrorCategory.RECOVERABLE

    def test_recoverable_guardrail(self) -> None:
        assert classify_error({"error": "Guardrail soft failure"}) == ErrorCategory.RECOVERABLE

    def test_recoverable_validation_error(self) -> None:
        assert classify_error({"error": "Validation error in schema"}) == ErrorCategory.RECOVERABLE

    def test_unknown_defaults_recoverable(self) -> None:
        assert classify_error({"error": "Something went wrong"}) == ErrorCategory.RECOVERABLE

    def test_uses_message_key(self) -> None:
        assert classify_error({"message": "Connection refused"}) == ErrorCategory.RETRYABLE

    def test_fatal_checked_before_retryable(self) -> None:
        # "timeout" is retryable but "fatal" might appear; fatal indicators checked first
        assert classify_error({"error": "model not found"}) == ErrorCategory.FATAL


# -----------------------------------------------------------------------------
# Circuit breaker
# -----------------------------------------------------------------------------


class TestCircuitBreaker:
    """Tests for consecutive failure tracking and escalation."""

    def test_record_failure_increments(self) -> None:
        state = ProjectState(project_id="cb1", current_phase=ProjectPhase.PLANNING)
        assert get_consecutive_failures(state, ProjectPhase.PLANNING) == 0
        assert record_failure(state, ProjectPhase.PLANNING) == 1
        assert record_failure(state, ProjectPhase.PLANNING) == 2
        assert get_consecutive_failures(state, ProjectPhase.PLANNING) == 2

    def test_reset_circuit(self) -> None:
        state = ProjectState(project_id="cb2", current_phase=ProjectPhase.DEVELOPMENT)
        record_failure(state, ProjectPhase.DEVELOPMENT)
        record_failure(state, ProjectPhase.DEVELOPMENT)
        reset_circuit(state, ProjectPhase.DEVELOPMENT)
        assert get_consecutive_failures(state, ProjectPhase.DEVELOPMENT) == 0

    def test_circuit_breaker_should_escalate_at_threshold(self) -> None:
        state = ProjectState(project_id="cb3", current_phase=ProjectPhase.TESTING)
        assert circuit_breaker_should_escalate(state, ProjectPhase.TESTING) is False
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            record_failure(state, ProjectPhase.TESTING)
        assert circuit_breaker_should_escalate(state, ProjectPhase.TESTING) is True

    def test_consecutive_failures_per_phase(self) -> None:
        state = ProjectState(project_id="cb4", current_phase=ProjectPhase.PLANNING)
        record_failure(state, ProjectPhase.PLANNING)
        record_failure(state, ProjectPhase.PLANNING)
        record_failure(state, ProjectPhase.DEVELOPMENT)
        assert get_consecutive_failures(state, ProjectPhase.PLANNING) == 2
        assert get_consecutive_failures(state, ProjectPhase.DEVELOPMENT) == 1


# -----------------------------------------------------------------------------
# Recovery action
# -----------------------------------------------------------------------------


class TestGetRecoveryAction:
    """Tests for get_recovery_action."""

    def test_fatal_escalates(self) -> None:
        state = ProjectState(project_id="r1", current_phase=ProjectPhase.PLANNING)
        action, payload = get_recovery_action(ErrorCategory.FATAL, state, ProjectPhase.PLANNING)
        assert action == "escalate"
        assert "reason" in payload

    def test_retryable_retries_until_max(self) -> None:
        state = ProjectState(project_id="r2", current_phase=ProjectPhase.PLANNING, max_retries=2)
        action, payload = get_recovery_action(ErrorCategory.RETRYABLE, state, ProjectPhase.PLANNING)
        assert action == "retry"
        assert payload.get("backoff_attempt") == 0
        record_failure(state, ProjectPhase.PLANNING)
        record_failure(state, ProjectPhase.PLANNING)
        action2, _ = get_recovery_action(ErrorCategory.RETRYABLE, state, ProjectPhase.PLANNING)
        assert action2 == "escalate"

    def test_recoverable_retry_with_feedback(self) -> None:
        state = ProjectState(project_id="r3", current_phase=ProjectPhase.DEVELOPMENT)
        action, payload = get_recovery_action(
            ErrorCategory.RECOVERABLE, state, ProjectPhase.DEVELOPMENT
        )
        assert action == "retry_with_feedback"
        assert "feedback" in payload

    def test_circuit_breaker_overrides_retryable(self) -> None:
        state = ProjectState(project_id="r4", current_phase=ProjectPhase.TESTING)
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            record_failure(state, ProjectPhase.TESTING)
        action, payload = get_recovery_action(
            ErrorCategory.RETRYABLE, state, ProjectPhase.TESTING
        )
        assert action == "escalate"
        assert payload.get("reason") == "circuit_breaker"


# -----------------------------------------------------------------------------
# Backoff
# -----------------------------------------------------------------------------


class TestBackoff:
    """Tests for get_backoff_delay and apply_retry_backoff."""

    def test_backoff_delays_match_constant(self) -> None:
        for i in range(len(RETRY_BACKOFF_DELAYS)):
            assert get_backoff_delay(i) == float(RETRY_BACKOFF_DELAYS[i])

    def test_backoff_caps_at_last(self) -> None:
        assert get_backoff_delay(100) == float(RETRY_BACKOFF_DELAYS[-1])

    def test_apply_retry_backoff_sleeps(self) -> None:
        # Just ensure it doesn't raise; we don't want long sleeps in tests
        apply_retry_backoff(0)


# -----------------------------------------------------------------------------
# State preservation
# -----------------------------------------------------------------------------


class TestStatePreservation:
    """Tests for persist_state_on_error, load_state_from_file, rollback_last_phase."""

    def test_persist_and_load_roundtrip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from ai_team.flows import error_handling as eh
        settings = MagicMock()
        settings.project.output_dir = str(tmp_path)
        monkeypatch.setattr(eh, "get_settings", lambda: settings)

        state = ProjectState(project_id="persist1", current_phase=ProjectPhase.PLANNING)
        state.project_description = "Test project"
        path = persist_state_on_error(state)
        assert path.exists()
        loaded = load_state_from_file(path)
        assert loaded.project_id == state.project_id
        assert loaded.current_phase == state.current_phase

    def test_load_state_resets_consecutive_failures(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Loaded state has consecutive_failures_* reset to 0 so a new run does not inherit old counts."""
        from ai_team.flows import error_handling as eh
        settings = MagicMock()
        settings.project.output_dir = str(tmp_path)
        monkeypatch.setattr(eh, "get_settings", lambda: settings)

        state = ProjectState(project_id="reset1", current_phase=ProjectPhase.PLANNING)
        record_failure(state, ProjectPhase.PLANNING)
        record_failure(state, ProjectPhase.PLANNING)
        path = persist_state_on_error(state)
        loaded = load_state_from_file(path)
        assert get_consecutive_failures(loaded, ProjectPhase.PLANNING) == 0

    def test_rollback_last_phase(self) -> None:
        state = ProjectState(project_id="roll1", current_phase=ProjectPhase.DEVELOPMENT)
        state.add_phase_transition(ProjectPhase.PLANNING, ProjectPhase.DEVELOPMENT, "Done")
        prev = rollback_last_phase(state)
        assert prev == ProjectPhase.PLANNING
        assert state.current_phase == ProjectPhase.PLANNING
        assert len(state.phase_history) == 0

    def test_rollback_empty_history_returns_none(self) -> None:
        state = ProjectState(project_id="roll2", current_phase=ProjectPhase.PLANNING)
        assert rollback_last_phase(state) is None


# -----------------------------------------------------------------------------
# Error reporting
# -----------------------------------------------------------------------------


class TestErrorReporting:
    """Tests for build_error_summary_report and get_error_metrics."""

    def test_summary_report_includes_errors(self) -> None:
        state = ProjectState(project_id="rep1", current_phase=ProjectPhase.TESTING)
        state.add_error(ProjectPhase.PLANNING, "planning_error", "Timeout", recoverable=True)
        state.add_error(ProjectPhase.DEVELOPMENT, "dev_error", "Invalid format", recoverable=True)
        report = build_error_summary_report(state)
        assert "rep1" in report
        assert "Timeout" in report
        assert "Invalid format" in report
        assert "2" in report or "Total errors" in report

    def test_metrics_error_count_by_phase(self) -> None:
        state = ProjectState(project_id="m1", current_phase=ProjectPhase.DEPLOYMENT)
        state.add_error(ProjectPhase.PLANNING, "e1", "msg1", recoverable=True)
        state.add_error(ProjectPhase.PLANNING, "e2", "msg2", recoverable=True)
        state.add_error(ProjectPhase.DEVELOPMENT, "e3", "msg3", recoverable=True)
        metrics = get_error_metrics(state)
        assert metrics["total_errors"] == 3
        assert metrics["error_count_by_phase"]["planning"] == 2
        assert metrics["error_count_by_phase"]["development"] == 1

    def test_structured_error_log(self) -> None:
        entry = record_structured_error(
            phase=ProjectPhase.PLANNING,
            error_type="timeout",
            message="Request timed out",
            agent="product_owner",
        )
        assert entry.phase == "planning"
        assert entry.error_type == "timeout"
        assert entry.agent == "product_owner"


# -----------------------------------------------------------------------------
# Handler entry points
# -----------------------------------------------------------------------------


class TestHandlerEntryPoints:
    """Tests for handle_planning_error, handle_development_error, etc."""

    def test_handle_planning_error_returns_action(self) -> None:
        state = ProjectState(project_id="h1", current_phase=ProjectPhase.PLANNING)
        result = handle_planning_error(state, {"error": "Connection refused"})
        assert "action" in result
        assert result["phase"] == "planning"
        assert result["status"] == "error"
        assert "summary_report" in result
        assert "metrics" in result
        assert len(state.errors) == 1

    def test_handle_development_error_fatal_escalates(self) -> None:
        state = ProjectState(project_id="h2", current_phase=ProjectPhase.DEVELOPMENT)
        result = handle_development_error(state, {"error": "model not found"})
        assert result["action"] == "escalate"
        assert state.current_phase == ProjectPhase.ERROR

    def test_handle_testing_error_retryable_retries(self) -> None:
        state = ProjectState(project_id="h3", current_phase=ProjectPhase.TESTING)
        result = handle_testing_error(state, {"error": "Request timed out"})
        assert result["action"] in ("retry", "escalate")
        assert "category" in result
        assert result["category"] == "retryable"

    def test_handle_deployment_error_recoverable(self) -> None:
        state = ProjectState(project_id="h4", current_phase=ProjectPhase.DEPLOYMENT)
        result = handle_deployment_error(state, {"error": "Invalid output format"})
        assert result["action"] == "retry_with_feedback"
        assert "structured_log" in result
