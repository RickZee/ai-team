"""Unit tests for manager self-improvement report builder."""

from __future__ import annotations

from ai_team.reports.manager_self_improvement import (
    build_manager_self_improvement_report,
    render_manager_self_improvement_markdown,
)


def test_build_report_has_backend_sections_and_proposals() -> None:
    report = build_manager_self_improvement_report(
        backend="langgraph",
        run_id="test-run-id",
        team_profile="backend-api",
        state={
            "current_phase": "error",
            "project_id": "test-run-id",
            "errors": [
                {
                    "phase": "testing",
                    "type": "GuardrailError",
                    "message": "Output deviates from task scope (relevance 40% below 50%).",
                }
            ],
            "metadata": {"team_profile": "backend-api"},
        },
    )
    assert report["run"]["backend"] == "langgraph"
    assert "langgraph" in report["backends"]
    assert "crewai" in report["backends"]
    assert report["this_run"]["errors"]
    assert report["proposed_self_improvement"]


def test_render_markdown_contains_headers() -> None:
    report = build_manager_self_improvement_report(
        backend="crewai",
        run_id="x",
        team_profile="full",
        state={"current_phase": "complete", "errors": [], "metadata": {}},
    )
    md = render_manager_self_improvement_markdown(report)
    assert "# Manager self-improvement report" in md
    assert "## Reference: backends" in md
    assert "## Proposed self-improvement actions" in md


def test_render_markdown_includes_llm_narrative_when_present() -> None:
    report = build_manager_self_improvement_report(
        backend="langgraph",
        run_id="r1",
        team_profile="backend-api",
        state={"current_phase": "complete", "errors": [], "metadata": {}},
    )
    report["llm_narrative_summary"] = "Paragraph one.\n\nParagraph two."
    md = render_manager_self_improvement_markdown(report)
    assert "## Manager narrative (LLM)" in md
    assert "Paragraph one." in md
