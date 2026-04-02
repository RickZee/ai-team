"""Unit tests for backend comparison report models."""

from __future__ import annotations

from ai_team.core.result import ProjectResult
from ai_team.models.comparison_report import (
    BackendRunSnapshot,
    ComparisonReport,
    snapshot_from_project_result,
)


def test_snapshot_from_project_result_claude_raw() -> None:
    """Claude backend stores generated_files and session_id on raw payload."""
    pr = ProjectResult(
        backend_name="claude-agent-sdk",
        success=True,
        raw={
            "generated_files": ["a.py", "b.py"],
            "session_id": "claude-sess-1",
            "phases": [{"phase": "planning", "status": "completed"}],
        },
        team_profile="full",
    )
    snap = snapshot_from_project_result(
        backend_name="claude-agent-sdk",
        team_profile="full",
        duration_sec=0.5,
        result=pr,
    )
    assert snap.generated_files_count == 2
    assert snap.thread_id == "claude-sess-1"
    assert snap.current_phase == "planning"


def test_snapshot_from_project_result_langgraph_state() -> None:
    """LangGraph raw uses ``state`` + ``thread_id``."""
    pr = ProjectResult(
        backend_name="langgraph",
        success=True,
        raw={
            "state": {
                "current_phase": "complete",
                "generated_files": [{"path": "a.py"}, {"path": "b.py"}],
            },
            "thread_id": "tid-1",
        },
        team_profile="full",
    )
    snap = snapshot_from_project_result(
        backend_name="langgraph",
        team_profile="full",
        duration_sec=1.25,
        result=pr,
    )
    assert snap.success is True
    assert snap.thread_id == "tid-1"
    assert snap.current_phase == "complete"
    assert snap.generated_files_count == 2
    assert abs(snap.duration_sec - 1.25) < 0.001


def test_comparison_report_markdown_contains_metrics() -> None:
    """Markdown output lists both backends."""
    report = ComparisonReport(
        demo_path="/tmp/demos/x",
        description="Build a REST API for todos",
        env="dev",
        team_profile="full",
        crewai=BackendRunSnapshot(
            backend_name="crewai",
            team_profile="full",
            success=True,
            duration_sec=10.0,
            current_phase="complete",
            generated_files_count=3,
        ),
        langgraph=BackendRunSnapshot(
            backend_name="langgraph",
            team_profile="full",
            success=True,
            duration_sec=2.5,
            thread_id="abc",
            current_phase="complete",
            generated_files_count=3,
        ),
    )
    md = report.to_markdown()
    assert "CrewAI" in md or "crewai" in md.lower()
    assert "LangGraph" in md or "langgraph" in md.lower()
    assert "10.000" in md or "10.0" in md
    assert "REST API" in report.description


def test_to_json_dict_roundtrip_keys() -> None:
    """``to_json_dict`` includes nested snapshots."""
    report = ComparisonReport(
        demo_path="d",
        description="x",
        env=None,
        team_profile="full",
        crewai=BackendRunSnapshot(
            backend_name="crewai",
            team_profile="full",
            success=False,
            duration_sec=0.1,
            error="boom",
        ),
        langgraph=BackendRunSnapshot(
            backend_name="langgraph",
            team_profile="full",
            success=True,
            duration_sec=0.2,
        ),
    )
    d = report.to_json_dict()
    assert d["crewai"]["error"] == "boom"
    assert d["langgraph"]["success"] is True
