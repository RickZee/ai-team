"""
Frontend Developer agent.

Uses DeveloperBase with frontend-specific tools (component_generator,
state_management, api_client_generator). YAML config defines role, goal, backstory.
Specializes in React, Vue, HTML/CSS/JS, Tailwind.
Generates components, pages, styles, API client code.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ai_team.agents.developer_base import DeveloperBase, create_developer_agent
from ai_team.tools.developer_tools import get_frontend_developer_tools


class FrontendDeveloper(DeveloperBase):
    """Frontend developer with component/state/API-client tools."""

    pass


def create_frontend_developer(
    *,
    tools: list[Any] | None = None,
    before_task: Callable[[str, dict[str, Any]], None] | None = None,
    after_task: Callable[[str, Any], None] | None = None,
    guardrail_tools: bool = True,
    config_path: Path | None = None,
    agents_config: dict[str, Any] | None = None,
    **kwargs: Any,
) -> FrontendDeveloper:
    """Create a FrontendDeveloper from agents.yaml."""
    return create_developer_agent(
        "frontend_developer",
        FrontendDeveloper,
        tool_getter=get_frontend_developer_tools,
        tools=tools,
        before_task=before_task,
        after_task=after_task,
        guardrail_tools=guardrail_tools,
        config_path=config_path,
        agents_config=agents_config,
        default_role="Senior Frontend Developer",
        **kwargs,
    )
