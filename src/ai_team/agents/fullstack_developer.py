"""
Fullstack Developer agent.

Combines backend and frontend capabilities in one agent. Used for simple projects
that don't need separate frontend/backend agents. Uses DeveloperBase with all
developer tools (common + backend + frontend).
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from ai_team.agents.base import _load_agents_config
from ai_team.agents.developer_base import DeveloperBase
from ai_team.tools.developer_tools import get_fullstack_developer_tools


class FullstackDeveloper(DeveloperBase):
    """
    Fullstack developer with all developer tools: common (code_generation,
    file_writer, dependency_resolver, code_reviewer) plus backend
    (database_schema_design, api_implementation, orm_generator) and frontend
    (component_generator, state_management, api_client_generator).

    Used for simple projects that don't need separate frontend/backend agents.
    """

    pass


def create_fullstack_developer(
    *,
    tools: Optional[List[Any]] = None,
    before_task: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    after_task: Optional[Callable[[str, Any], None]] = None,
    guardrail_tools: bool = True,
    config_path: Optional[Path] = None,
    agents_config: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> FullstackDeveloper:
    """
    Create a FullstackDeveloper from agents.yaml (fullstack_developer entry).

    :param tools: Optional override for full tool list.
    :param before_task: Optional callback before task.
    :param after_task: Optional callback after task.
    :param guardrail_tools: Wrap tools with guardrails.
    :param config_path: Override path to agents YAML.
    :param agents_config: Pre-loaded config dict (overrides file).
    :param kwargs: Passed to DeveloperBase.
    :return: Configured FullstackDeveloper instance.
    """
    if agents_config is None:
        if config_path and config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                agents_config = yaml.safe_load(f) or {}
        else:
            agents_config = _load_agents_config()

    role_key = "fullstack_developer"
    if role_key not in agents_config:
        raise KeyError(f"'{role_key}' not in agents config. Known: {list(agents_config.keys())}")

    cfg = agents_config[role_key]
    all_tools = None if tools is not None else get_fullstack_developer_tools()
    return FullstackDeveloper(
        role_name=role_key,
        role=cfg.get("role", "Senior Fullstack Developer"),
        goal=cfg.get("goal", ""),
        backstory=cfg.get("backstory", ""),
        tools=tools if tools is not None else all_tools,
        extra_tools=None,
        verbose=cfg.get("verbose", True),
        allow_delegation=cfg.get("allow_delegation", False),
        max_iter=cfg.get("max_iter", 15),
        memory=cfg.get("memory", True),
        before_task=before_task,
        after_task=after_task,
        guardrail_tools=guardrail_tools,
        **kwargs,
    )
