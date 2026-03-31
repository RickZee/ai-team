"""Integration-style tests for LangGraph placeholder main graph (no LLM)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from ai_team.backends.langgraph_backend.graphs.main_graph import compile_main_graph


def _base_state(description: str) -> dict:
    return {
        "project_description": description,
        "project_id": str(uuid4()),
        "current_phase": "intake",
        "phase_history": [],
        "errors": [],
        "retry_count": 0,
        "max_retries": 3,
        "messages": [],
        "generated_files": [],
        "metadata": {},
    }


@pytest.mark.integration
def test_placeholder_graph_short_description_reaches_error() -> None:
    """Routing after intake sends too-short descriptions to the error terminal."""
    graph = compile_main_graph()
    init = _base_state("short")
    final = graph.invoke(init, {"configurable": {"thread_id": "integration-short-desc"}})
    assert final.get("current_phase") == "error"
