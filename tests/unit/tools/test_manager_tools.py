"""Unit tests for ``manager_tools`` (delegation, timeline, blockers, status, factory)."""

from __future__ import annotations

from ai_team.tools.manager_tools import (
    BlockerResolutionTool,
    StatusReportingTool,
    TaskDelegationTool,
    TimelineManagementTool,
    get_manager_tools,
)
from crewai.tools import BaseTool


class TestTaskDelegationTool:
    def test_recommends_qa_for_testing_skills(self) -> None:
        out = TaskDelegationTool().run(
            task_description="Add pytest coverage for checkout",
            required_skills=["testing", "automation"],
            priority="high",
        )
        assert "qa_engineer" in out
        assert "high" in out
        assert "checkout" in out or "pytest" in out.lower()

    def test_recommends_architect_for_architecture_skill(self) -> None:
        out = TaskDelegationTool().run(
            task_description="Design service boundaries",
            required_skills=["architecture"],
        )
        assert "architect" in out

    def test_recommends_devops_for_docker_skill(self) -> None:
        out = TaskDelegationTool().run(
            task_description="Fix CI pipeline",
            required_skills=["docker", "ci_cd"],
        )
        assert "devops_engineer" in out

    def test_empty_skills_still_returns_assignment(self) -> None:
        out = TaskDelegationTool().run(task_description="General coordination")
        assert "Recommended assignment:" in out
        assert "**" in out


class TestTimelineManagementTool:
    def test_includes_phase_and_milestones(self) -> None:
        out = TimelineManagementTool().run(
            current_phase="development",
            completed_milestones="M1, M2",
            next_milestones="M3",
            risks_or_delays="None",
        )
        assert "development" in out
        assert "M1" in out or "M2" in out
        assert "M3" in out
        assert "ProjectState" in out or "phase_history" in out


class TestBlockerResolutionTool:
    def test_records_blocker_and_default_phase(self) -> None:
        out = BlockerResolutionTool().run(blocker_description="API rate limited")
        assert "API rate limited" in out
        assert "unknown" in out.lower() or "Affected phase" in out

    def test_includes_suggested_actions(self) -> None:
        out = BlockerResolutionTool().run(
            blocker_description="Schema migration conflict",
            affected_phase="testing",
            suggested_actions="Rollback and retry",
        )
        assert "testing" in out
        assert "Rollback" in out


class TestStatusReportingTool:
    def test_builds_report_lines(self) -> None:
        out = StatusReportingTool().run(
            current_phase="planning",
            summary="Requirements signed off",
            project_id="proj-1",
        )
        assert "proj-1" in out
        assert "planning" in out
        assert "Requirements" in out

    def test_optional_fields_included_when_set(self) -> None:
        out = StatusReportingTool().run(
            current_phase="intake",
            summary="Kickoff done",
            phase_suggestion="planning",
            blockers="waiting on access",
            state_updates_json='{"foo": 1}',
        )
        assert "planning" in out
        assert "waiting on access" in out
        assert "foo" in out


class TestGetManagerTools:
    def test_returns_four_tools(self) -> None:
        tools = get_manager_tools()
        assert len(tools) == 4
        names = {t.name for t in tools}
        assert names == {
            "task_delegation",
            "timeline_management",
            "blocker_resolution",
            "status_reporting",
        }
        assert all(isinstance(t, BaseTool) for t in tools)
