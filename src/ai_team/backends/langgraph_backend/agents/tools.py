"""
Per-role LangChain tool lists for the LangGraph backend.

Mirrors the tool wiring used by CrewAI agent factories (``create_*_agent``).
"""

from __future__ import annotations

from ai_team.backends.common.role_tools import CREW_TOOLS
from ai_team.tools.langchain_adapter import to_langchain_tools
from langchain_core.tools import BaseTool as LangChainBaseTool

# Role key -> factory that returns CrewAI tools (functions or BaseTool instances).
# The map lives in backends.common so new backends cannot grow a private copy.
_CREW_TOOLS = CREW_TOOLS


def get_langchain_tools_for_role(role_key: str) -> list[LangChainBaseTool]:
    """
    Return LangChain-native tools for ``role_key`` (``agents.yaml`` keys).

    Raises:
        KeyError: Unknown role.
    """
    if role_key not in _CREW_TOOLS:
        available = ", ".join(sorted(_CREW_TOOLS))
        raise KeyError(f"Unknown role {role_key!r} for LangGraph tools. Available: {available}")
    crew_tools = _CREW_TOOLS[role_key]()
    return to_langchain_tools(crew_tools)
