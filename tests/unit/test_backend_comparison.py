"""Unit tests for ``compare_backends`` utilities (mocked backends)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_team.core.result import ProjectResult
from ai_team.utils.backend_comparison import compare_backends_on_description


def test_compare_backends_on_description_uses_both_backends() -> None:
    """``get_backend`` is called for crewai and langgraph; report has both snapshots."""
    pr_c = ProjectResult(
        backend_name="crewai",
        success=True,
        raw={
            "state": {
                "current_phase": "complete",
                "generated_files": [],
            },
        },
        team_profile="full",
    )
    pr_l = ProjectResult(
        backend_name="langgraph",
        success=True,
        raw={
            "state": {"current_phase": "complete", "generated_files": []},
            "thread_id": "t-99",
        },
        team_profile="full",
    )

    def fake_get(name: str) -> MagicMock:
        b = MagicMock()
        b.name = name
        if name == "crewai":
            b.run.return_value = pr_c
        else:
            b.run.return_value = pr_l
        return b

    with patch("ai_team.utils.backend_comparison.get_backend", side_effect=fake_get):
        report = compare_backends_on_description(
            description="A" * 20,
            demo_path=Path("/tmp/demo"),
            team="full",
            env=None,
            skip_estimate=True,
            complexity_override=None,
        )

    assert report.crewai.backend_name == "crewai"
    assert report.langgraph.backend_name == "langgraph"
    assert report.langgraph.thread_id == "t-99"
    assert report.crewai.success and report.langgraph.success
