"""
Per-role LangChain tool lists for the LangGraph backend.

Mirrors the tool wiring used by CrewAI agent factories (``create_*_agent``).
"""

from __future__ import annotations

from collections.abc import Callable

from ai_team.tools.architect_tools import get_architect_tools
from ai_team.tools.developer_tools import (
    get_backend_developer_tools,
    get_developer_common_tools,
    get_frontend_developer_tools,
    get_fullstack_developer_tools,
)
from ai_team.tools.infrastructure import CLOUD_TOOLS, DEVOPS_TOOLS
from ai_team.tools.langchain_adapter import to_langchain_tools
from ai_team.tools.manager_tools import get_manager_tools
from ai_team.tools.product_owner import get_product_owner_tools
from ai_team.tools.qa_tools import get_qa_tools
from ai_team.tools.rag_search import search_knowledge
from langchain_core.tools import BaseTool as LangChainBaseTool

# Role key -> factory that returns CrewAI tools (functions or BaseTool instances)
_CREW_TOOLS: dict[str, Callable[[], list]] = {
    "manager": get_manager_tools,
    "product_owner": get_product_owner_tools,
    "architect": get_architect_tools,
    "backend_developer": lambda: list(get_developer_common_tools())
    + list(get_backend_developer_tools()),
    "frontend_developer": lambda: list(get_developer_common_tools())
    + list(get_frontend_developer_tools()),
    "fullstack_developer": get_fullstack_developer_tools,
    "devops_engineer": lambda: list(DEVOPS_TOOLS),
    "cloud_engineer": lambda: list(CLOUD_TOOLS),
    "qa_engineer": get_qa_tools,
}


def get_langchain_tools_for_role(role_key: str) -> list[LangChainBaseTool]:
    """
    Return LangChain-native tools for ``role_key`` (``agents.yaml`` keys).

    When ``RAG_ENABLED`` is true, appends :func:`search_knowledge` for all roles.

    Raises:
        KeyError: Unknown role.
    """
    if role_key not in _CREW_TOOLS:
        available = ", ".join(sorted(_CREW_TOOLS))
        raise KeyError(f"Unknown role {role_key!r} for LangGraph tools. Available: {available}")
    crew_tools = _CREW_TOOLS[role_key]()
    out = to_langchain_tools(crew_tools)
    from ai_team.rag.config import get_rag_config

    if get_rag_config().enabled:
        out = list(out) + [search_knowledge]
    return out
