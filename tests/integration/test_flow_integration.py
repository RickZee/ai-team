"""Integration tests for the main flow (requires Ollama when fully wired)."""

import pytest
from ai_team.flows.main_flow import run_ai_team


@pytest.mark.integration
def test_run_ai_team_returns_result() -> None:
    """run_ai_team returns a dict with result and state."""
    out = run_ai_team("Create a hello world API")
    assert "result" in out
    assert "state" in out
    assert isinstance(out["state"], dict)
