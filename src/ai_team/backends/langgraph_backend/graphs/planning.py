"""Planning subgraph: supervisor (manager) + product owner + architect ReAct agents."""

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

PLANNING_WORKERS = ("product_owner", "architect")
PLANNING_SUPERVISOR_NAME = "planning_supervisor"

_STRUCTURED_OUTPUT_INSTRUCTIONS = """
## Required structured output
At the end of your response, you MUST output two fenced JSON blocks in this exact order:

1) Requirements:
```json
{ "requirements": { "functional": [], "non_functional": [], "constraints": [], "acceptance_criteria": [] } }
```

2) Architecture:
```json
{ "architecture": { "overview": "", "components": [], "data_flow": [], "interfaces": [], "risks": [] } }
```

The JSON must be valid (no trailing commas). Keep prose above the JSON blocks.
""".strip()


def _make_worker(
    role_key: str,
    name: str,
    llm: BaseChatModel,
) -> CompiledStateGraph:
    prompt = load_agent_prompt(role_key).system_message() + "\n\n" + _STRUCTURED_OUTPUT_INSTRUCTIONS
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


def compile_planning_subgraph(
    *,
    agents: frozenset[str] | None = None,
    model_overrides: dict[str, str] | None = None,
    manager_llm: BaseChatModel | None = None,
    product_owner_llm: BaseChatModel | None = None,
    architect_llm: BaseChatModel | None = None,
) -> CompiledStateGraph:
    """
    Compile the planning supervisor: Manager delegates to Product Owner and Architect.

    When ``agents`` is provided, only workers present in that set are wired.
    ``model_overrides`` maps role keys to model IDs that replace the settings default.

    Returns a compiled graph whose state includes ``messages`` (handoff + ReAct) and
    Phase-5 guardrail nodes after the agent subgraph.
    """
    overrides = model_overrides or {}
    active_workers = [w for w in PLANNING_WORKERS if agents is None or w in agents]

    if not active_workers:
        logger.info("planning_subgraph_passthrough", reason="no workers in profile")
        return _passthrough_subgraph()

    def _llm_for(role: str, explicit: BaseChatModel | None) -> BaseChatModel:
        if explicit is not None:
            return explicit
        return create_chat_model_for_role(role, model_id_override=overrides.get(role))

    m_llm = _llm_for("manager", manager_llm)

    worker_agents = []
    for role in active_workers:
        llm_map = {"product_owner": product_owner_llm, "architect": architect_llm}
        worker_agents.append(_make_worker(role, role, _llm_for(role, llm_map.get(role))))

    if len(worker_agents) == 1:
        core = worker_agents[0]
        behavioral_role = active_workers[0]
        logger.info("planning_subgraph_compiled", workers=active_workers, mode="single_agent")
    else:
        supervisor_prompt = (
            load_agent_prompt("manager").system_message()
            + "\n\n"
            + _STRUCTURED_OUTPUT_INSTRUCTIONS
        )
        workflow = create_supervisor(
            worker_agents,
            model=m_llm,
            prompt=supervisor_prompt,
            add_handoff_messages=True,
            supervisor_name=PLANNING_SUPERVISOR_NAME,
            state_schema=LangGraphSubgraphState,
        )
        core = workflow.compile()
        behavioral_role = "manager"
        logger.info("planning_subgraph_compiled", workers=active_workers, mode="supervisor")

    return wrap_agents_with_guardrails(
        core,
        behavioral_role=behavioral_role,
        behavioral_only_message_names=frozenset({PLANNING_SUPERVISOR_NAME}),
    )
