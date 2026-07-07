"""Smoke test: compiled LangGraph runs end-to-end with dummy state."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from ai_team.backends.langgraph_backend.graphs import main_graph as mg
from ai_team.backends.langgraph_backend.graphs.main_graph import compile_main_graph

from tests.unit.backends.langgraph_backend.harness import graph_invoke


def test_main_graph_invoke_reaches_complete() -> None:
    graph = compile_main_graph()
    final = graph_invoke(graph, thread_id="unit-test-thread")
    assert final.get("current_phase") == "complete"
    assert final.get("project_id") == "unit-test-thread"


def test_intake_binds_project_id_from_thread_id_not_uuid() -> None:
    """Mismatched ``project_id`` in seed state is corrected at intake."""
    graph = compile_main_graph()
    wrong_id = str(uuid4())
    final = graph_invoke(
        graph,
        thread_id="bound-thread",
        project_id=wrong_id,
    )
    assert final.get("project_id") == "bound-thread"
    assert final.get("project_id") != wrong_id


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
        final = graph_invoke(graph, thread_id="smoke-loop-thread")

    assert final.get("current_phase") == "complete"
    assert calls["n"] >= 2  # smoke ran again after the retry
    assert int(final.get("retry_count") or 0) >= 1  # development was re-run


def test_compile_main_graph_full_mode_builds() -> None:
    """Full mode compiles (subgraphs lazy until invoke)."""
    graph = compile_main_graph(mode="full")
    assert graph is not None
