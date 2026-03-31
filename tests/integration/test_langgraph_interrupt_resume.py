"""Minimal LangGraph interrupt + ``Command(resume=...)`` (HITL contract)."""

from __future__ import annotations

from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class _TinyState(TypedDict, total=False):
    """State for a one-node graph that blocks on interrupt."""

    value: int


def _node_hitl(_state: _TinyState) -> dict[str, int]:
    """Return user input from interrupt payload (mirrors main graph HITL)."""
    feedback = interrupt({"phase": "review"})
    return {"value": int(feedback) if feedback is not None else 0}


@pytest.mark.integration
def test_interrupt_then_command_resume() -> None:
    """Stream yields interrupt; second ``invoke`` with ``Command(resume=...)`` completes."""
    g = StateGraph(_TinyState)
    g.add_node("human_review", _node_hitl)
    g.add_edge(START, "human_review")
    g.add_edge("human_review", END)
    app = g.compile(checkpointer=MemorySaver())
    cfg: dict = {"configurable": {"thread_id": "hitl-integration"}}

    saw_interrupt = False
    for chunk in app.stream({"value": 0}, cfg, stream_mode="updates"):
        if "__interrupt__" in chunk:
            saw_interrupt = True
    assert saw_interrupt is True

    final = app.invoke(Command(resume=7), cfg)
    assert final.get("value") == 7
