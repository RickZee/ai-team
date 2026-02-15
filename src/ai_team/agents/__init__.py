"""CrewAI agent definitions (Manager, Product Owner, Architect, Developers, QA, DevOps, Cloud)."""

from ai_team.agents.base import BaseAgent, create_agent
from ai_team.agents.developer_base import DeveloperBase
from ai_team.agents.backend_developer import BackendDeveloper, create_backend_developer
from ai_team.agents.frontend_developer import FrontendDeveloper, create_frontend_developer
from ai_team.agents.fullstack_developer import FullstackDeveloper, create_fullstack_developer
from ai_team.agents.architect import (
    create_architect_agent,
    validate_architecture_against_requirements,
)
from ai_team.agents.manager import (
    HUMAN_ESCALATION_CONFIDENCE_THRESHOLD,
    create_manager_agent,
)
from ai_team.agents.product_owner import (
    create_product_owner_agent,
    get_template_for_project_type,
    requirements_from_agent_output,
    validate_requirements_document,
    validate_requirements_guardrail,
)
from ai_team.agents.devops_engineer import DevOpsEngineer, create_devops_engineer
from ai_team.agents.cloud_engineer import CloudEngineer, create_cloud_engineer
from ai_team.agents.qa_engineer import (
    create_qa_engineer,
    feedback_for_developers,
    quality_gate_passed,
)

__all__ = [
    "BaseAgent",
    "create_agent",
    "DeveloperBase",
    "BackendDeveloper",
    "create_backend_developer",
    "FrontendDeveloper",
    "create_frontend_developer",
    "FullstackDeveloper",
    "create_fullstack_developer",
    "create_architect_agent",
    "create_manager_agent",
    "create_product_owner_agent",
    "get_template_for_project_type",
    "HUMAN_ESCALATION_CONFIDENCE_THRESHOLD",
    "requirements_from_agent_output",
    "validate_architecture_against_requirements",
    "validate_requirements_document",
    "validate_requirements_guardrail",
    "DevOpsEngineer",
    "create_devops_engineer",
    "CloudEngineer",
    "create_cloud_engineer",
    "create_qa_engineer",
    "feedback_for_developers",
    "quality_gate_passed",
]
