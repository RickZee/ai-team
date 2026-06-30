"""
Backend Developer agent.

Uses DeveloperBase with backend-specific tools (database_schema_design,
api_implementation, orm_generator). YAML config defines role, goal, backstory.
Specializes in Python (Flask/FastAPI/Django), Node.js (Express), Go.
Generates source files, requirements.txt/package.json, database migrations.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ai_team.agents.developer_base import DeveloperBase, create_developer_agent
from ai_team.tools.developer_tools import get_backend_developer_tools


class BackendDeveloper(DeveloperBase):
    """
    Backend developer agent with common developer tools plus backend-specific:
    database_schema_design, api_implementation, orm_generator.

    Specializes in: Python (Flask/FastAPI/Django), Node.js (Express), Go.
    Generates: source files, requirements.txt/package.json, database migrations.
    """

    pass


def create_backend_developer(
    *,
    tools: list[Any] | None = None,
    before_task: Callable[[str, dict[str, Any]], None] | None = None,
    after_task: Callable[[str, Any], None] | None = None,
    guardrail_tools: bool = True,
    config_path: Path | None = None,
    agents_config: dict[str, Any] | None = None,
    **kwargs: Any,
) -> BackendDeveloper:
    """Create a BackendDeveloper from agents.yaml (backend_developer entry)."""
    return create_developer_agent(
        "backend_developer",
        BackendDeveloper,
        tool_getter=get_backend_developer_tools,
        tools=tools,
        before_task=before_task,
        after_task=after_task,
        guardrail_tools=guardrail_tools,
        config_path=config_path,
        agents_config=agents_config,
        default_role="Senior Backend Developer",
        **kwargs,
    )
