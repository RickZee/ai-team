"""Smoke test: compiled LangGraph runs end-to-end with dummy state."""

from __future__ import annotations

from uuid import uuid4

from ai_team.backends.langgraph_backend.graphs.main_graph import compile_main_graph


def test_main_graph_invoke_reaches_complete() -> None:
    graph = compile_main_graph()
    init = {
        "project_description": "x" * 20,
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
    final = graph.invoke(init, {"configurable": {"thread_id": "unit-test-thread"}})
    assert final.get("current_phase") == "complete"


def test_compile_main_graph_full_mode_builds() -> None:
    """Full mode compiles (subgraphs lazy until invoke)."""
    graph = compile_main_graph(mode="full")
    assert graph is not None
