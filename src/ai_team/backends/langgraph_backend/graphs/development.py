"""Development subgraph: supervisor (manager) + backend, frontend, fullstack ReAct agents."""

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
from langgraph_supervisor import create_supervisor

logger = structlog.get_logger(__name__)

DEVELOPMENT_WORKERS = ("backend_developer", "frontend_developer", "fullstack_developer")
DEVELOPMENT_SUPERVISOR_NAME = "development_supervisor"


def _make_worker(
    role_key: str,
    name: str,
    llm: BaseChatModel,
) -> CompiledStateGraph:
    prompt = load_agent_prompt(role_key).system_message()
    tools = get_langchain_tools_for_role(role_key)
    return create_react_agent(
        llm,
        tools,
        prompt=prompt,
        name=name,
        state_schema=LangGraphSubgraphState,
    )


def _passthrough_subgraph() -> CompiledStateGraph:
    """Minimal graph that returns state unchanged (no workers in profile)."""

    def noop(_state: LangGraphSubgraphState) -> dict[str, Any]:
        return {}

    g = StateGraph(LangGraphSubgraphState)
    g.add_node("noop", noop)
    g.add_edge(START, "noop")
    g.add_edge("noop", END)
    return g.compile()


def compile_development_subgraph(
    *,
    agents: frozenset[str] | None = None,
    model_overrides: dict[str, str] | None = None,
    manager_llm: BaseChatModel | None = None,
    backend_llm: BaseChatModel | None = None,
    frontend_llm: BaseChatModel | None = None,
    fullstack_llm: BaseChatModel | None = None,
) -> CompiledStateGraph:
    """
    Compile development supervisor: Manager routes among backend, frontend, fullstack.

    When ``agents`` is provided, only workers present in that set are wired.
    ``model_overrides`` maps role keys to model IDs that replace the settings default.
    """
    overrides = model_overrides or {}
    active_workers = [w for w in DEVELOPMENT_WORKERS if agents is None or w in agents]

    if not active_workers:
        logger.info("development_subgraph_passthrough", reason="no workers in profile")
        return _passthrough_subgraph()

    explicit_llms: dict[str, BaseChatModel | None] = {
        "backend_developer": backend_llm,
        "frontend_developer": frontend_llm,
        "fullstack_developer": fullstack_llm,
    }

    def _llm_for(role: str) -> BaseChatModel:
        explicit = explicit_llms.get(role)
        if explicit is not None:
            return explicit
        return create_chat_model_for_role(role, model_id_override=overrides.get(role))

    worker_agents = [_make_worker(role, role, _llm_for(role)) for role in active_workers]

    if len(worker_agents) == 1:
        core = worker_agents[0]
        behavioral_role = active_workers[0]
        logger.info("development_subgraph_compiled", workers=active_workers, mode="single_agent")
    else:
        m_llm = manager_llm or create_chat_model_for_role(
            "manager", model_id_override=overrides.get("manager")
        )
        supervisor_prompt = load_agent_prompt("manager").system_message()
        workflow = create_supervisor(
            worker_agents,
            model=m_llm,
            prompt=supervisor_prompt,
            add_handoff_messages=True,
            supervisor_name=DEVELOPMENT_SUPERVISOR_NAME,
            state_schema=LangGraphSubgraphState,
        )
        core = workflow.compile()
        behavioral_role = "manager"
        logger.info("development_subgraph_compiled", workers=active_workers, mode="supervisor")

    return wrap_agents_with_guardrails(
        core,
        behavioral_role=behavioral_role,
        behavioral_only_message_names=frozenset({DEVELOPMENT_SUPERVISOR_NAME}),
    )
