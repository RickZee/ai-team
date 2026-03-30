"""LangChain/CrewAI-compatible ``search_knowledge`` tool backed by RAG."""

from __future__ import annotations

import structlog
from ai_team.rag.config import get_rag_config
from ai_team.rag.pipeline import get_rag_pipeline
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)


@tool
def search_knowledge(query: str, top_k: int = 5) -> str:
    """
    Search the semantic knowledge base (markdown guides under ``ai_team/knowledge``).

    Use for architecture, security, testing, Docker, and framework conventions.
    """
    cfg = get_rag_config()
    if not cfg.enabled:
        return "RAG is disabled (set RAG_ENABLED=true and ingest knowledge)."
    if not (query or "").strip():
        return "Provide a non-empty query."
    try:
        pipe = get_rag_pipeline()
        k = top_k if top_k > 0 else cfg.top_k
        hits = pipe.retrieve(query.strip(), top_k=k)
        if not hits:
            return "No matching snippets found."
        return pipe.format_context(hits)
    except Exception as e:
        logger.warning("search_knowledge_failed", error=str(e))
        return f"Knowledge search failed: {e}"


def get_search_knowledge_tool():
    """Return the tool object (for adapters that need the callable)."""
    return search_knowledge
