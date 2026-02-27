"""Unit tests for planning output parsing: _looks_like_architecture and _parse_planning_output."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ai_team.flows.main_flow import (
    _looks_like_architecture,
    _parse_planning_output,
)


class TestLooksLikeArchitecture:
    """_looks_like_architecture rejects health-check / wrong schema, accepts architecture-like dicts."""

    def test_accepts_system_overview(self) -> None:
        assert _looks_like_architecture({"system_overview": "A REST API.", "components": []}) is True

    def test_accepts_components_only(self) -> None:
        assert _looks_like_architecture({"components": [{"name": "API", "responsibilities": "HTTP"}]}) is True

    def test_rejects_health_check(self) -> None:
        assert _looks_like_architecture({"status": "ok", "version": "1.0"}) is False

    def test_rejects_status_only(self) -> None:
        assert _looks_like_architecture({"status": "ok"}) is False

    def test_rejects_non_dict(self) -> None:
        assert _looks_like_architecture("not a dict") is False
        assert _looks_like_architecture(None) is False


class TestParsePlanningOutputRejectsWrongSchema:
    """When second task output is health-check-like JSON, we get fallback architecture, not validation error."""

    def test_health_check_second_task_uses_fallback_architecture(self) -> None:
        """LLM sometimes returns {"status": "ok", "version": "1.0"} for architecture task; we use fallback."""
        req_raw = '{"project_name": "Test", "description": "API", "user_stories": []}'
        arch_raw = '{"status": "ok", "version": "1.0"}'
        crew_result = MagicMock()
        crew_result.tasks_output = [
            MagicMock(raw=req_raw),
            MagicMock(raw=arch_raw),
        ]
        requirements, architecture, needs_clarification = _parse_planning_output(crew_result)
        assert requirements is not None
        assert architecture is not None
        assert "could not be parsed" in architecture.system_overview or "invalid schema" in architecture.system_overview
        assert architecture.components == []
