"""Inspect LangGraph checkpoint state for debugging (thread id + config)."""

from __future__ import annotations

from typing import Any

import structlog
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot

logger = structlog.get_logger(__name__)


def get_thread_state_snapshot(
    graph: CompiledStateGraph,
    thread_id: str,
) -> StateSnapshot:
    """
    Return the latest checkpoint snapshot for ``thread_id``.

    Requires the graph to have been compiled with a checkpointer.
    """
    config = {"configurable": {"thread_id": thread_id}}
    return graph.get_state(config)


def describe_thread_state(
    graph: CompiledStateGraph,
    thread_id: str,
) -> dict[str, Any]:
    """
    Serializable summary of ``get_state`` for logging or CLI debugging.
    """
    snap = get_thread_state_snapshot(graph, thread_id)
    out: dict[str, Any] = {
        "thread_id": thread_id,
        "values_keys": (list(snap.values.keys()) if isinstance(snap.values, dict) else None),
        "next": list(snap.next) if snap.next else [],
        "tasks": len(snap.tasks) if snap.tasks else 0,
        "metadata": snap.metadata,
    }
    logger.debug("langgraph_thread_state_described", **out)
    return out
