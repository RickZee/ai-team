"""Shared helpers for LangGraph subgraph builders."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ai_team.backends.langgraph_backend.graphs.state import LangGraphSubgraphState
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent


def passthrough_subgraph() -> CompiledStateGraph:
    """Return a no-op subgraph that passes state through unchanged."""

    def noop(state: LangGraphSubgraphState) -> dict[str, Any]:
        return {}

    builder: StateGraph = StateGraph(LangGraphSubgraphState)
    builder.add_node("noop", noop)
    builder.add_edge(START, "noop")
    builder.add_edge("noop", END)
    return builder.compile()


def build_react_worker(
    *,
    role_key: str,
    name: str,
    llm: BaseChatModel,
    system_prompt: str,
    tools: list[Any],
) -> CompiledStateGraph:
    """Create a ReAct agent worker for a subgraph role."""
    return create_react_agent(
        llm,
        tools=tools,
        name=name,
        state_modifier=system_prompt,
    )


def resolve_role_llm(
    role_key: str,
    explicit: BaseChatModel | None,
    overrides: dict[str, BaseChatModel] | None,
    factory: Callable[[str], BaseChatModel],
) -> BaseChatModel:
    """Pick explicit override, profile override, or factory default."""
    if explicit is not None:
        return explicit
    if overrides and role_key in overrides:
        return overrides[role_key]
    return factory(role_key)
