"""Unit tests for planning output parsing: _looks_like_architecture and _parse_planning_output."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from ai_team.backends.crewai_backend.flows.main_flow import (
    _looks_like_architecture,
    _parse_planning_output,
)


class TestLooksLikeArchitecture:
    """_looks_like_architecture rejects health-check / wrong schema, accepts architecture-like dicts."""

    def test_accepts_system_overview(self) -> None:
        assert (
            _looks_like_architecture({"system_overview": "A REST API.", "components": []}) is True
        )

    def test_accepts_components_only(self) -> None:
        assert (
            _looks_like_architecture({"components": [{"name": "API", "responsibilities": "HTTP"}]})
            is True
        )

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
        assert (
            "could not be parsed" in architecture.system_overview
            or "invalid schema" in architecture.system_overview
        )
        assert architecture.components == []


def test_stubbed_planning_writes_acceptance(tmp_path: Path) -> None:
    """Definition of done for harness-alignment 1.3: planning produces ACCEPTANCE.json."""
    from ai_team.harness.acceptance import write_initial
    from ai_team.harness.receipt import ReceiptWriter
    from ai_team.models.requirements import (
        AcceptanceCriterion,
        MoSCoW,
        RequirementsDocument,
        UserStory,
    )

    from evals.trace.builder import TraceBuilder

    req = RequirementsDocument(
        project_name="todo-api",
        description="todos",
        user_stories=[
            UserStory(
                as_a="user",
                i_want="list todos",
                so_that="I can plan",
                acceptance_criteria=[AcceptanceCriterion(description="GET /todos returns 200")],
                priority=MoSCoW.MUST,
            )
        ],
    )
    write_initial(tmp_path, req, "plan-1")
    assert (tmp_path / "ACCEPTANCE.json").is_file()
    rec = ReceiptWriter().write_from_run(
        output_dir=tmp_path / "out",
        workspace=tmp_path,
        run_id="plan-1",
        backend="crewai",
        smoke={"ran": False, "skip_reason": "planning only"},
    )
    assert rec.acceptance_path == "ACCEPTANCE.json"
    assert rec.acceptance_item_count is not None and rec.acceptance_item_count >= 1
    (tmp_path / "logs").mkdir(exist_ok=True)
    trace = TraceBuilder(backend="crewai", tier="A").from_workspace(tmp_path)
    assert any(a.path == "ACCEPTANCE.json" for a in trace.artifacts)
