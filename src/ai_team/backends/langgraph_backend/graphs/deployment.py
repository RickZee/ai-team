"""Deployment subgraph: DevOps then Cloud engineer (sequential ReAct agents)."""

from __future__ import annotations

from typing import Any

import structlog
from ai_team.backends.langgraph_backend.agents.prompts import load_agent_prompt
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

DEPLOYMENT_WORKERS = ("devops_engineer", "cloud_engineer")


def compile_deployment_subgraph(
    *,
    agents: frozenset[str] | None = None,
    model_overrides: dict[str, str] | None = None,
    devops_llm: BaseChatModel | None = None,
    cloud_llm: BaseChatModel | None = None,
) -> CompiledStateGraph:
    """
    Sequential pipeline: DevOps agent produces CI/CD artifacts, then Cloud agent for IaC.

    When ``agents`` is provided, only workers present in that set are wired.
    ``model_overrides`` maps role keys to model IDs that replace the settings default.
    """
    overrides = model_overrides or {}
    active_workers = [w for w in DEPLOYMENT_WORKERS if agents is None or w in agents]

    if not active_workers:
        logger.info("deployment_subgraph_passthrough", reason="no workers in profile")

        def noop(_state: LangGraphSubgraphState) -> dict[str, Any]:
            return {}

        g = StateGraph(LangGraphSubgraphState)
        g.add_node("noop", noop)
        g.add_edge(START, "noop")
        g.add_edge("noop", END)
        return g.compile()

    explicit_llms: dict[str, BaseChatModel | None] = {
        "devops_engineer": devops_llm,
        "cloud_engineer": cloud_llm,
    }

    def _llm_for(role: str) -> BaseChatModel:
        explicit = explicit_llms.get(role)
        if explicit is not None:
            return explicit
        return create_chat_model_for_role(role, model_id_override=overrides.get(role))

    def _make_agent(role: str) -> CompiledStateGraph:
        prompt = load_agent_prompt(role).system_message()
        tools = get_langchain_tools_for_role(role)
        return create_react_agent(
            _llm_for(role),
            tools,
            prompt=prompt,
            name=role,
            state_schema=LangGraphSubgraphState,
        )

    if len(active_workers) == 1:
        sole = active_workers[0]
        core = _make_agent(sole)
        logger.info("deployment_subgraph_compiled", sequence=active_workers, mode="single_agent")
        return wrap_agents_with_guardrails(core, behavioral_role=sole)

    g = StateGraph(LangGraphSubgraphState)
    prev: str | None = None
    for role in active_workers:
        g.add_node(role, _make_agent(role))
        if prev is None:
            g.add_edge(START, role)
        else:
            g.add_edge(prev, role)
        prev = role
    g.add_edge(active_workers[-1], END)

    logger.info("deployment_subgraph_compiled", sequence=active_workers, mode="sequential")
    core = g.compile()
    return wrap_agents_with_guardrails(core, behavioral_role=active_workers[0])
