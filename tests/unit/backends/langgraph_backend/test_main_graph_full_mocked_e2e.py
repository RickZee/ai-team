"""
Main LangGraph (``mode=full``) end-to-end tests with mocked subgraph nodes.

Avoids real LLM calls while exercising conditional edges, retry loop, and error routing.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from ai_team.backends.langgraph_backend.graphs import subgraph_runners as sr
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


@pytest.fixture(autouse=True)
def _reset_subgraph_cache() -> None:
    sr.reset_subgraph_cache()
    yield
    sr.reset_subgraph_cache()


def test_full_mode_graph_completes_with_stub_subgraph_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All four phase subgraphs are replaced; run reaches ``complete``."""

    def plan(*_a: object, **_k: object) -> dict:
        return {
            "current_phase": "planning",
            "requirements": {"stub": True},
            "architecture": {"stub": True},
        }

    def dev(*_a: object, **_k: object) -> dict:
        return {
            "current_phase": "development",
            "generated_files": [{"path": "app.py"}],
        }

    def test(*_a: object, **_k: object) -> dict:
        return {"current_phase": "testing", "test_results": {"passed": True}}

    def deploy(*_a: object, **_k: object) -> dict:
        return {
            "current_phase": "deployment",
            "deployment_config": {"status": "ok"},
        }

    monkeypatch.setattr(sr, "planning_subgraph_node", plan)
    monkeypatch.setattr(sr, "development_subgraph_node", dev)
    monkeypatch.setattr(sr, "testing_subgraph_node", test)
    monkeypatch.setattr(sr, "deployment_subgraph_node", deploy)

    g = compile_main_graph(mode="full")
    final = g.invoke(_base_state("y" * 20), {"configurable": {"thread_id": "e2e-stub"}})
    assert final.get("current_phase") == "complete"


def test_full_mode_retry_loop_then_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    """Testing fails once → ``retry_development`` → pass → ``complete``."""

    def plan(*_a: object, **_k: object) -> dict:
        return {
            "current_phase": "planning",
            "requirements": {"stub": True},
            "architecture": {"stub": True},
        }

    def dev(*_a: object, **_k: object) -> dict:
        return {
            "current_phase": "development",
            "generated_files": [{"path": "fix.py"}],
        }

    attempts = {"n": 0}

    def test(*_a: object, **_k: object) -> dict:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return {"current_phase": "testing", "test_results": {"passed": False}}
        return {"current_phase": "testing", "test_results": {"passed": True}}

    def deploy(*_a: object, **_k: object) -> dict:
        return {"current_phase": "deployment", "deployment_config": {"ok": True}}

    monkeypatch.setattr(sr, "planning_subgraph_node", plan)
    monkeypatch.setattr(sr, "development_subgraph_node", dev)
    monkeypatch.setattr(sr, "testing_subgraph_node", test)
    monkeypatch.setattr(sr, "deployment_subgraph_node", deploy)

    g = compile_main_graph(mode="full")
    final = g.invoke(_base_state("z" * 20), {"configurable": {"thread_id": "e2e-retry"}})
    assert final.get("current_phase") == "complete"
    assert int(final.get("retry_count") or 0) >= 1


def test_full_mode_planning_error_routes_to_error_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Errors after planning route to ``error`` and END."""

    def plan_err(*_a: object, **_k: object) -> dict:
        return {
            "errors": [
                {
                    "phase": "planning",
                    "message": "simulated failure",
                    "type": "RuntimeError",
                }
            ],
            "current_phase": "planning",
        }

    monkeypatch.setattr(sr, "planning_subgraph_node", plan_err)

    g = compile_main_graph(mode="full")
    final = g.invoke(_base_state("w" * 20), {"configurable": {"thread_id": "e2e-err"}})
    assert final.get("current_phase") == "error"


def test_planning_subgraph_node_maps_subgraph_exception_to_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``planning_subgraph_node`` wraps subgraph ``invoke`` failures in ``errors``."""

    class _BadGraph:
        def invoke(self, *_a: object, **_k: object) -> dict:
            raise RuntimeError("subgraph invoke failed")

    monkeypatch.setattr(sr, "_cached_planning", lambda _a, _o: _BadGraph())

    from ai_team.backends.langgraph_backend.graphs.subgraph_runners import (
        planning_subgraph_node,
    )

    out = planning_subgraph_node(
        {
            "project_description": "x" * 30,
            "messages": [],
            "errors": [],
            "requirements": {},
            "architecture": {},
            "generated_files": [],
            "metadata": {"agents": ["manager", "product_owner", "architect"]},
        },
        {"configurable": {"thread_id": "unit-planning-exc"}},
    )
    assert out.get("errors")
    assert "subgraph invoke failed" in (out["errors"][0].get("message") or "")


def test_placeholder_graph_planning_hitl_then_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Placeholder planning requests human → human_review → development → … → complete."""
    import ai_team.backends.langgraph_backend.graphs.main_graph as mg

    def plan_hitl(*_a: object, **_k: object) -> dict:
        return {
            "current_phase": "planning",
            "metadata": {"planning_needs_human": True},
        }

    monkeypatch.setattr(mg, "_node_planning", plan_hitl)
    g = compile_main_graph(mode="placeholder")
    final = g.invoke(
        _base_state("h" * 20),
        {"configurable": {"thread_id": "placeholder-hitl"}},
    )
    assert final.get("current_phase") == "complete"


def test_placeholder_testing_escalates_to_human_then_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``testing_needs_human`` routes to human_review → retry_development → complete."""
    import ai_team.backends.langgraph_backend.graphs.main_graph as mg

    visits = {"testing": 0}

    def fake_testing(*_a: object, **_k: object) -> dict:
        visits["testing"] += 1
        if visits["testing"] == 1:
            return {
                "current_phase": "testing",
                "metadata": {"testing_needs_human": True},
                "test_results": {"passed": True},
            }
        return {
            "current_phase": "testing",
            "metadata": {"testing_needs_human": False},
            "test_results": {"passed": True},
        }

    monkeypatch.setattr(mg, "_node_testing", fake_testing)
    g = compile_main_graph(mode="placeholder")
    final = g.invoke(
        _base_state("t" * 20),
        {"configurable": {"thread_id": "placeholder-test-hitl"}},
    )
    assert final.get("current_phase") == "complete"
    assert visits["testing"] >= 2
