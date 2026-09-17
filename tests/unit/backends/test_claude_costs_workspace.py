"""Unit tests for Claude backend cost log helpers and workspace profile."""

from __future__ import annotations

from pathlib import Path

from ai_team.backends.claude_agent_sdk_backend.costs import (
    append_cost_log,
    cost_comparison_markdown,
    read_cost_log,
    remaining_budget_usd,
    total_logged_cost_usd,
)
from ai_team.backends.claude_agent_sdk_backend.workspace import write_profile_claude_context
from ai_team.core.team_profile import TeamProfile


def test_cost_log_roundtrip_and_totals(tmp_path: Path) -> None:
    append_cost_log(tmp_path, phase="orchestrator", cost_usd=0.5, usage={"x": 1})
    append_cost_log(tmp_path, phase="orchestrator", cost_usd=0.25, usage=None)
    rows = read_cost_log(tmp_path)
    assert len(rows) == 2
    assert total_logged_cost_usd(tmp_path) == 0.75
    assert remaining_budget_usd(tmp_path, 1.0) == 0.25


def test_cost_comparison_markdown_includes_ceiling(tmp_path: Path) -> None:
    append_cost_log(tmp_path, phase="orchestrator", cost_usd=1.0, usage={})
    md = cost_comparison_markdown(tmp_path, crewai_estimate_usd=0.5, ceiling_usd=5.0)
    assert "Logged spend" in md
    assert "Ceiling" in md
    assert "CrewAI estimate" in md


def test_write_profile_claude_context_creates_file(tmp_path: Path) -> None:
    profile = TeamProfile(
        name="p1",
        agents=["qa_engineer"],
        phases=["testing"],
        metadata={"rag": {"knowledge_topics": ["pytest"]}},
    )
    write_profile_claude_context(tmp_path, profile)
    text = (tmp_path / "docs" / "CLAUDE_PROFILE.md").read_text(encoding="utf-8")
    assert "p1" in text
    assert "qa_engineer" in text
    assert "pytest" in text


def test_default_total_budget_respects_run_budget_env(monkeypatch) -> None:
    """A lab that sets AI_TEAM_RUN_BUDGET_USD=1 must not run Claude with an $18 ceiling."""
    from ai_team.backends.claude_agent_sdk_backend.costs import (
        PHASE_BUDGETS_USD,
        default_total_budget_usd,
    )

    phase_sum = float(sum(PHASE_BUDGETS_USD.values()))
    monkeypatch.setenv("AI_TEAM_RUN_BUDGET_USD", "1")
    assert default_total_budget_usd() == 1.0
    monkeypatch.setenv("AI_TEAM_RUN_BUDGET_USD", "500")
    assert default_total_budget_usd() == phase_sum
    for value in ("0", "", "nope"):
        monkeypatch.setenv("AI_TEAM_RUN_BUDGET_USD", value)
        assert default_total_budget_usd() == phase_sum
    monkeypatch.delenv("AI_TEAM_RUN_BUDGET_USD")
    assert default_total_budget_usd() == phase_sum
