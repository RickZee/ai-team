"""Integration-style tests for LangGraph placeholder main graph (no LLM)."""

from __future__ import annotations

import os

import pytest
from ai_team.backends.langgraph_backend.graphs.main_graph import compile_main_graph

from tests.unit.backends.langgraph_backend.harness import graph_invoke


@pytest.fixture(autouse=True)
def _langgraph_integration_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_TEAM_SKIP_POST_RUN", "1")


@pytest.mark.integration
def test_placeholder_graph_short_description_reaches_error() -> None:
    """Routing after intake sends too-short descriptions to the error terminal."""
    graph = compile_main_graph()
    final = graph_invoke(graph, thread_id="integration-short-desc", description="short")
    assert final.get("current_phase") == "error"
    assert final.get("project_id") == "integration-short-desc"


@pytest.mark.integration
def test_placeholder_graph_does_not_write_to_repo_workspace(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    """Graph tests must not litter ``./workspace`` with run directories."""
    repo_ws = os.path.abspath("workspace")
    before = set(os.listdir(repo_ws)) if os.path.isdir(repo_ws) else set()
    ws = tmp_path / "workspace"
    ws.mkdir()
    graph = compile_main_graph()
    graph_invoke(graph, thread_id="isolated-thread", workspace=ws)
    after = set(os.listdir(repo_ws)) if os.path.isdir(repo_ws) else set()
    assert after == before
