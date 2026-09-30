"""Role prompts loaded from ``config/agents.yaml``.

New backends call this module. The text is the LangGraph system prompt, so
the nine roles cannot drift into a second copy.
"""

from __future__ import annotations

from ai_team.backends.langgraph_backend.agents.prompts import (
    AgentPromptBundle,
    build_system_prompt,
    list_agent_role_keys,
    load_agent_prompt,
)


def load_role(role_key: str) -> AgentPromptBundle:
    """Return goal, backstory, and title for ``role_key``."""
    return load_agent_prompt(role_key)


def system_prompt_for_role(role_key: str) -> str:
    """System prompt for ``role_key``, including pinned lessons when present."""
    return build_system_prompt(role_key)


def role_keys() -> list[str]:
    """Every role key in ``agents.yaml``."""
    return list_agent_role_keys()
