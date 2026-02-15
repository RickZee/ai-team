"""
Agent definitions: Manager, Product Owner, Architect, developers, QA, etc.
"""

from ai_team.agents.backend_developer import get_backend_developer_agent
from ai_team.agents.manager import get_manager_agent

__all__: list[str] = ["get_manager_agent", "get_backend_developer_agent"]
