"""Shared helpers for LangGraph graph tests (isolated workspace, aligned run ids)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_team.backends.langgraph_backend.run_session import RunSession


def base_graph_state(
    *,
    thread_id: str,
    description: str = "x" * 20,
    **overrides: Any,
) -> dict[str, Any]:
    """Build initial state with ``project_id`` aligned to *thread_id*."""
    state: dict[str, Any] = {
        "project_description": description,
        "project_id": thread_id,
        "current_phase": "intake",
        "phase_history": [],
        "errors": [],
        "retry_count": 0,
        "max_retries": 3,
        "messages": [],
        "generated_files": [],
        "metadata": {},
    }
    state.update(overrides)
    return state


def graph_invoke(
    graph: Any,
    *,
    thread_id: str = "unit-test-thread",
    description: str = "x" * 20,
    workspace: Path | None = None,
    **state_overrides: Any,
) -> dict[str, Any]:
    """Invoke a compiled graph with run identity contract and optional tmp workspace."""
    init = base_graph_state(
        thread_id=thread_id,
        description=description,
        **state_overrides,
    )
    config = {"configurable": {"thread_id": thread_id}}
    if workspace is not None:
        with RunSession.open(
            run_id=thread_id,
            workspace_root=workspace,
            skip_post_run=True,
        ):
            return graph.invoke(init, config)
    return graph.invoke(init, config)
