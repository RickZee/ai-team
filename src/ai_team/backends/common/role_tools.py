"""Role → tool factories shared by every backend.

The map is the one LangGraph and CrewAI already use. New backends import it
instead of keeping a private list.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ai_team.tools.architect_tools import get_architect_tools
from ai_team.tools.developer_tools import (
    get_backend_developer_tools,
    get_developer_common_tools,
    get_frontend_developer_tools,
    get_fullstack_developer_tools,
)
from ai_team.tools.infrastructure import CLOUD_TOOLS, DEVOPS_TOOLS
from ai_team.tools.manager_tools import get_manager_tools
from ai_team.tools.product_owner import get_product_owner_tools
from ai_team.tools.qa_tools import get_qa_tools

CrewToolFactory = Callable[[], list[Any]]

CREW_TOOLS: dict[str, CrewToolFactory] = {
    "manager": get_manager_tools,
    "product_owner": get_product_owner_tools,
    "architect": get_architect_tools,
    "backend_developer": lambda: (
        list(get_developer_common_tools()) + list(get_backend_developer_tools())
    ),
    "frontend_developer": lambda: (
        list(get_developer_common_tools()) + list(get_frontend_developer_tools())
    ),
    "fullstack_developer": get_fullstack_developer_tools,
    "devops_engineer": lambda: list(DEVOPS_TOOLS),
    "cloud_engineer": lambda: list(CLOUD_TOOLS),
    "qa_engineer": get_qa_tools,
}


def crew_tools_for_role(role_key: str) -> list[Any]:
    """Return the CrewAI tool objects configured for ``role_key``."""
    if role_key not in CREW_TOOLS:
        available = ", ".join(sorted(CREW_TOOLS))
        raise KeyError(f"Unknown role {role_key!r}. Available: {available}")
    return list(CREW_TOOLS[role_key]())
