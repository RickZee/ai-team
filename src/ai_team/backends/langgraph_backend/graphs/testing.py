"""Testing subgraph: single QA engineer ReAct agent."""

from __future__ import annotations

from typing import Any

import structlog
from ai_team.backends.langgraph_backend.agents.prompts import build_system_prompt
from ai_team.backends.langgraph_backend.agents.tools import get_langchain_tools_for_role
from ai_team.backends.langgraph_backend.graphs.langgraph_chat import (
    create_chat_model_for_role,
)
from ai_team.backends.langgraph_backend.graphs.langgraph_guardrail_nodes import (
    wrap_agents_with_guardrails,
)
from ai_team.backends.langgraph_backend.graphs.state import LangGraphSubgraphState
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

logger = structlog.get_logger(__name__)


def compile_testing_subgraph(
    *,
    agents: frozenset[str] | None = None,
    model_overrides: dict[str, str] | None = None,
    qa_llm: BaseChatModel | None = None,
) -> CompiledStateGraph:
    """Compile QA ReAct agent with test/QA tools and Phase-5 guardrail nodes.

    When ``agents`` is provided and ``qa_engineer`` is absent, returns a pass-through.
    """
    if agents is not None and "qa_engineer" not in agents:
        logger.info("testing_subgraph_passthrough", reason="qa_engineer not in profile")

        def noop(_state: LangGraphSubgraphState) -> dict[str, Any]:
            return {}

        g = StateGraph(LangGraphSubgraphState)
        g.add_node("noop", noop)
        g.add_edge(START, "noop")
        g.add_edge("noop", END)
        return g.compile()

    overrides = model_overrides or {}
    llm = qa_llm or create_chat_model_for_role(
        "qa_engineer", model_id_override=overrides.get("qa_engineer")
    )
    prompt = build_system_prompt("qa_engineer")
    tools = get_langchain_tools_for_role("qa_engineer")
    agent = create_react_agent(
        llm,
        tools,
        prompt=prompt,
        name="qa_engineer",
        state_schema=LangGraphSubgraphState,
    )
    logger.info("testing_subgraph_compiled", agent="qa_engineer")
    return wrap_agents_with_guardrails(agent, behavioral_role="qa_engineer")
