"""
Frontend Developer agent.

Uses DeveloperBase with frontend-specific tools (component_generator,
state_management, api_client_generator). YAML config defines role, goal, backstory.
Specializes in React, Vue, HTML/CSS/JS, Tailwind.
Generates components, pages, styles, API client code.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from ai_team.agents.base import _load_agents_config
from ai_team.agents.developer_base import DeveloperBase
from ai_team.tools.developer_tools import get_frontend_developer_tools


class FrontendDeveloper(DeveloperBase):
    """
    Frontend developer agent with common developer tools plus frontend-specific:
    component_generator, state_management, api_client_generator.

    Specializes in: React, Vue, HTML/CSS/JS, Tailwind.
    Generates: components, pages, styles, API client code.
    """

    pass


def create_frontend_developer(
    *,
    tools: Optional[List[Any]] = None,
    before_task: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    after_task: Optional[Callable[[str, Any], None]] = None,
    guardrail_tools: bool = True,
    config_path: Optional[Path] = None,
    agents_config: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> FrontendDeveloper:
    """
    Create a FrontendDeveloper from agents.yaml (frontend_developer entry).

    :param tools: Optional override for full tool list.
    :param before_task: Optional callback before task.
    :param after_task: Optional callback after task.
    :param guardrail_tools: Wrap tools with guardrails.
    :param config_path: Override path to agents YAML.
    :param agents_config: Pre-loaded config dict (overrides file).
    :param kwargs: Passed to DeveloperBase.
    :return: Configured FrontendDeveloper instance.
    """
    if agents_config is None:
        if config_path and config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                agents_config = yaml.safe_load(f) or {}
        else:
            agents_config = _load_agents_config()

    role_key = "frontend_developer"
    if role_key not in agents_config:
        raise KeyError(f"'{role_key}' not in agents config. Known: {list(agents_config.keys())}")

    cfg = agents_config[role_key]
    extra_tools = None if tools is not None else get_frontend_developer_tools()
    return FrontendDeveloper(
        role_name=role_key,
        role=cfg.get("role", "Senior Frontend Developer"),
        goal=cfg.get("goal", ""),
        backstory=cfg.get("backstory", ""),
        tools=tools,
        extra_tools=extra_tools,
        verbose=cfg.get("verbose", True),
        allow_delegation=cfg.get("allow_delegation", False),
        max_iter=cfg.get("max_iter", 15),
        memory=cfg.get("memory", True),
        before_task=before_task,
        after_task=after_task,
        guardrail_tools=guardrail_tools,
        **kwargs,
    )
