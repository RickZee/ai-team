"""Unit tests for ``ProjectState`` and phase transitions."""

from __future__ import annotations

import pytest
from ai_team.flows.state import ProjectPhase, ProjectState


class TestProjectStateDefaults:
    def test_default_phase_is_intake(self) -> None:
        s = ProjectState(project_description="x")
        assert s.current_phase == ProjectPhase.INTAKE

    def test_retry_counts_empty(self) -> None:
        s = ProjectState()
        assert s.retry_counts == {}


class TestProjectStateTransitions:
    def test_add_phase_transition_sequential(self) -> None:
        s = ProjectState()
        s.add_phase_transition(ProjectPhase.INTAKE, ProjectPhase.PLANNING)
        assert s.current_phase == ProjectPhase.PLANNING
        assert len(s.phase_history) == 1

    def test_invalid_skip_raises(self) -> None:
        s = ProjectState()
        with pytest.raises(ValueError, match="Invalid phase transition"):
            s.add_phase_transition(ProjectPhase.INTAKE, ProjectPhase.DEVELOPMENT)

    def test_error_transition_allowed(self) -> None:
        s = ProjectState()
        s.add_phase_transition(ProjectPhase.INTAKE, ProjectPhase.ERROR)
        assert s.current_phase == ProjectPhase.ERROR


class TestProjectStateRetry:
    def test_increment_retry(self) -> None:
        s = ProjectState(max_retries=3)
        s.increment_retry(ProjectPhase.PLANNING)
        assert s.retry_counts["planning"] == 1

    def test_increment_retry_limit(self) -> None:
        s = ProjectState(max_retries=1)
        s.increment_retry(ProjectPhase.PLANNING)
        with pytest.raises(ValueError, match="Retry limit"):
            s.increment_retry(ProjectPhase.PLANNING)

    def test_can_retry(self) -> None:
        s = ProjectState(max_retries=2)
        assert s.can_retry(ProjectPhase.PLANNING) is True
        s.increment_retry(ProjectPhase.PLANNING)
        s.increment_retry(ProjectPhase.PLANNING)
        assert s.can_retry(ProjectPhase.PLANNING) is False


class TestProjectStateErrors:
    def test_add_error(self) -> None:
        s = ProjectState()
        s.add_error(ProjectPhase.PLANNING, "E", "msg")
        assert len(s.errors) == 1
        assert s.errors[0].message == "msg"


class TestProjectStateSerialization:
    def test_model_dump_roundtrip(self) -> None:
        s = ProjectState(project_description="hello")
        d = s.model_dump()
        s2 = ProjectState.model_validate(d)
        assert s2.project_description == "hello"
