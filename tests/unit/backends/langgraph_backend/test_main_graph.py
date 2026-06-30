"""Smoke test: compiled LangGraph runs end-to-end with dummy state."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from ai_team.backends.langgraph_backend.graphs import main_graph as mg
from ai_team.backends.langgraph_backend.graphs.main_graph import compile_main_graph


def _init_state() -> dict:
    return {
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


def test_main_graph_invoke_reaches_complete() -> None:
    graph = compile_main_graph()
    final = graph.invoke(_init_state(), {"configurable": {"thread_id": "unit-test-thread"}})
    assert final.get("current_phase") == "complete"


def test_smoke_failure_loops_back_to_development_then_completes() -> None:
    """A failing runtime smoke must re-run development, then complete on a pass.

    Drives the real graph (placeholder mode) with the smoke node patched to fail
    once and then pass, proving the testing -> smoke -> retry_development ->
    development -> ... -> deployment loop is wired correctly.
    """
    calls = {"n": 0}

    def _flaky_smoke(state):  # noqa: ANN001
        meta = dict(state.get("metadata") or {})
        calls["n"] += 1
        ok = calls["n"] >= 2  # fail first, pass second
        meta["smoke_results"] = {"ran": True, "success": ok, "message": "x"}
        return {"current_phase": "smoke", "metadata": meta}

    with patch.object(mg, "_node_smoke_placeholder", _flaky_smoke):
        graph = compile_main_graph()
        final = graph.invoke(_init_state(), {"configurable": {"thread_id": "smoke-loop-thread"}})

    assert final.get("current_phase") == "complete"
    assert calls["n"] >= 2  # smoke ran again after the retry
    assert int(final.get("retry_count") or 0) >= 1  # development was re-run


def test_compile_main_graph_full_mode_builds() -> None:
    """Full mode compiles (subgraphs lazy until invoke)."""
    graph = compile_main_graph(mode="full")
    assert graph is not None
