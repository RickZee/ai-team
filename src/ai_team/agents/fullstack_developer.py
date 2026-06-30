"""
Fullstack Developer agent.

Combines backend and frontend capabilities in one agent. Used for simple projects
that don't need separate frontend/backend agents. Uses DeveloperBase with all
developer tools (common + backend + frontend).
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ai_team.agents.developer_base import DeveloperBase, create_developer_agent
from ai_team.tools.developer_tools import get_fullstack_developer_tools


class FullstackDeveloper(DeveloperBase):
    """Fullstack developer with all backend and frontend tools."""

    pass


def create_fullstack_developer(
    *,
    tools: list[Any] | None = None,
    before_task: Callable[[str, dict[str, Any]], None] | None = None,
    after_task: Callable[[str, Any], None] | None = None,
    guardrail_tools: bool = True,
    config_path: Path | None = None,
    agents_config: dict[str, Any] | None = None,
    **kwargs: Any,
) -> FullstackDeveloper:
    """Create a FullstackDeveloper from agents.yaml."""
    return create_developer_agent(
        "fullstack_developer",
        FullstackDeveloper,
        tools=tools if tools is not None else get_fullstack_developer_tools(),
        before_task=before_task,
        after_task=after_task,
        guardrail_tools=guardrail_tools,
        config_path=config_path,
        agents_config=agents_config,
        default_role="Senior Fullstack Developer",
        **kwargs,
    )
