"""Top-level LangGraph: placeholder or full subgraph wiring, HITL, Sqlite checkpointer."""

from __future__ import annotations

import sqlite3
from typing import Any, Literal

import structlog
from ai_team.backends.langgraph_backend.checkpointer import resolve_sqlite_checkpointer
from ai_team.backends.langgraph_backend.graphs.routing import (
    normalize_hitl_metadata,
    route_after_deployment,
    route_after_development,
    route_after_human_review,
    route_after_intake,
    route_after_planning,
    route_after_testing,
)
from ai_team.backends.langgraph_backend.graphs.state import LangGraphProjectState
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

logger = structlog.get_logger(__name__)

GraphMode = Literal["placeholder", "full"]


def _node_intake(state: LangGraphProjectState) -> dict[str, Any]:
    return {"current_phase": "intake"}


def _node_planning(state: LangGraphProjectState) -> dict[str, Any]:
    return {"current_phase": "planning"}


def _node_development(state: LangGraphProjectState) -> dict[str, Any]:
    return {"current_phase": "development"}


def _node_testing(state: LangGraphProjectState) -> dict[str, Any]:
    return {"current_phase": "testing"}


def _node_deployment(state: LangGraphProjectState) -> dict[str, Any]:
    return {"current_phase": "deployment"}


def _node_human_review_placeholder(state: LangGraphProjectState) -> dict[str, Any]:
    meta = normalize_hitl_metadata(state)
    return {"current_phase": "awaiting_human", "metadata": meta}


def _node_human_review_full(
    state: LangGraphProjectState,
    _config: RunnableConfig | None = None,
) -> dict[str, Any]:
    from langgraph.types import interrupt

    meta = normalize_hitl_metadata(state)
    payload = {
        "phase": "human_review",
        "hitl_source": meta.get("hitl_source"),
        "project_id": state.get("project_id"),
    }
    feedback = interrupt(payload)
    return {
        "human_feedback": str(feedback) if feedback is not None else "",
        "current_phase": "awaiting_human",
        "metadata": {**meta, "hitl_resumed": True},
    }


def _node_retry_development(state: LangGraphProjectState) -> dict[str, Any]:
    rc = int(state.get("retry_count") or 0)
    return {"retry_count": rc + 1, "current_phase": "development"}


def _node_complete(state: LangGraphProjectState) -> dict[str, Any]:
    return {"current_phase": "complete"}


def _node_error(state: LangGraphProjectState) -> dict[str, Any]:
    return {"current_phase": "error"}


def _node_manager_report(
    state: LangGraphProjectState,
    _config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Final manager step: write self-improvement report (JSON + Markdown) under output/reports."""
    from ai_team.core.results.writer import ResultsBundle
    from ai_team.reports.manager_self_improvement import write_manager_self_improvement_report

    meta = dict(state.get("metadata") or {})
    team = str(meta.get("team_profile") or "full")
    pid = str(state.get("project_id") or "").strip()
    if not pid:
        logger.warning("manager_report_skipped", reason="missing_project_id")
        return {}
    try:
        bundle = ResultsBundle(pid)
        write_manager_self_improvement_report(
            bundle,
            backend="langgraph",
            team_profile=team,
            state=state,
        )
        meta["manager_self_improvement_report"] = "reports/manager_self_improvement_report.md"
    except Exception as e:
        logger.warning("manager_report_failed", error=str(e))
    phase = str(state.get("current_phase") or "")
    return {"current_phase": phase, "metadata": meta}


def _node_rag_context(state: LangGraphProjectState) -> dict[str, Any]:
    """Inject semantic RAG snippets into ``metadata`` when ``RAG_ENABLED`` is set."""
    from ai_team.rag.config import get_rag_config

    if not get_rag_config().enabled:
        return {}
    q = (state.get("project_description") or "").strip()
    if not q:
        return {}
    try:
        from ai_team.rag.pipeline import get_rag_pipeline

        pipe = get_rag_pipeline()
        hits = pipe.retrieve(q, top_k=get_rag_config().top_k)
        meta = dict(state.get("metadata") or {})
        meta["rag_context"] = pipe.format_context(hits) if hits else ""
        return {"metadata": meta}
    except Exception as e:
        logger.warning("rag_context_node_failed", error=str(e))
        return {}


def build_main_graph(
    mode: GraphMode = "placeholder",
    *,
    rag_enabled: bool = False,
) -> StateGraph:
    """
    Wire nodes and conditional edges.

    * ``placeholder``: fast no-LLM stubs (default for unit tests).
    * ``full``: Phase-3 subgraphs for planning/development/testing/deployment.
    """
    g = StateGraph(LangGraphProjectState)
    g.add_node("intake", _node_intake)

    if mode == "full":
        from ai_team.backends.langgraph_backend.graphs.subgraph_runners import (
            deployment_subgraph_node,
            development_subgraph_node,
            planning_subgraph_node,
            testing_subgraph_node,
        )

        g.add_node("planning", planning_subgraph_node)
        g.add_node("development", development_subgraph_node)
        g.add_node("testing", testing_subgraph_node)
        g.add_node("deployment", deployment_subgraph_node)
        g.add_node("human_review", _node_human_review_full)
    else:
        g.add_node("planning", _node_planning)
        g.add_node("development", _node_development)
        g.add_node("testing", _node_testing)
        g.add_node("deployment", _node_deployment)
        g.add_node("human_review", _node_human_review_placeholder)

    g.add_node("retry_development", _node_retry_development)
    g.add_node("complete", _node_complete)
    g.add_node("error", _node_error)
    g.add_node("manager_report", _node_manager_report)

    if rag_enabled:
        g.add_node("rag_context", _node_rag_context)
        g.add_edge(START, "intake")
        g.add_edge("intake", "rag_context")
        g.add_conditional_edges(
            "rag_context",
            route_after_intake,
            {"planning": "planning", "error": "error"},
        )
    else:
        g.add_edge(START, "intake")
        g.add_conditional_edges(
            "intake",
            route_after_intake,
            {"planning": "planning", "error": "error"},
        )
    g.add_conditional_edges(
        "planning",
        route_after_planning,
        {
            "development": "development",
            "human_review": "human_review",
            "error": "error",
        },
    )
    g.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {"development": "development", "retry_development": "retry_development"},
    )
    g.add_conditional_edges(
        "development",
        route_after_development,
        {"testing": "testing", "error": "error"},
    )
    g.add_conditional_edges(
        "testing",
        route_after_testing,
        {
            "deployment": "deployment",
            "retry_development": "retry_development",
            "human_review": "human_review",
            "error": "error",
        },
    )
    g.add_edge("retry_development", "development")
    g.add_conditional_edges(
        "deployment",
        route_after_deployment,
        {"complete": "complete", "error": "error"},
    )
    g.add_edge("complete", "manager_report")
    g.add_edge("error", "manager_report")
    g.add_edge("manager_report", END)
    return g


def compile_main_graph(
    conn: sqlite3.Connection | None = None,
    mode: GraphMode = "placeholder",
    checkpointer: BaseCheckpointSaver | None = None,
    rag_enabled: bool | None = None,
) -> Any:
    """
    Compile the graph with a checkpointer (SQLite by default).

    ``conn``: explicit SQLite connection (e.g. tests use ``:memory:``).
    ``checkpointer``: override (e.g. Postgres from ``run_with_postgres_checkpointer``).
    ``rag_enabled``: when ``None``, uses :class:`ai_team.rag.config.RAGConfig`.
    """
    from ai_team.rag.config import get_rag_config

    re = rag_enabled if rag_enabled is not None else get_rag_config().enabled
    graph = build_main_graph(mode, rag_enabled=re)
    cp = checkpointer if checkpointer is not None else resolve_sqlite_checkpointer(conn)
    compiled = graph.compile(checkpointer=cp)
    logger.info(
        "langgraph_main_graph_compiled",
        mode=mode,
        rag_enabled=re,
        checkpointer=type(cp).__name__,
    )
    return compiled
