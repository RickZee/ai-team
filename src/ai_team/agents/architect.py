"""
Architect agent: designs scalable, maintainable architectures with clear interfaces.

Uses BaseAgent via create_agent("architect", tools=...). Output format is
ArchitectureDocument (system overview, components, technology stack, interface
contracts, data model outline, ASCII diagram, ADRs, deployment topology).

Pattern library: MVC, microservices, event-driven, CQRS, clean architecture.
Validates architecture against requirements document for completeness.
Guardrail: architecture must address all functional and non-functional requirements.
"""

from typing import List, Optional, Tuple

import structlog

from ai_team.agents.base import BaseAgent, create_agent
from ai_team.models.architecture import ArchitectureDocument
from ai_team.models.requirements import RequirementsDocument
from ai_team.tools.architect_tools import get_architect_tools

logger = structlog.get_logger(__name__)

# Pattern library the agent is expected to know (documented for task prompts)
ARCHITECTURE_PATTERNS = [
    "MVC (Model-View-Controller)",
    "microservices",
    "event-driven",
    "CQRS (Command Query Responsibility Segregation)",
    "clean architecture",
]


def validate_architecture_against_requirements(
    architecture: ArchitectureDocument,
    requirements: Optional[RequirementsDocument] = None,
) -> Tuple[bool, List[str]]:
    """
    Guardrail: verify the architecture addresses all functional and non-functional
    requirements. Returns (is_valid, list of missing or weak coverage items).

    If requirements is None, only structural completeness of the architecture
    is checked (overview, components, stack, interfaces, diagram, ADRs).
    """
    gaps: List[str] = []

    if not architecture.system_overview or len(architecture.system_overview.strip()) < 20:
        gaps.append("System overview is missing or too brief.")

    if not architecture.components:
        gaps.append("No components with responsibilities are defined.")

    if not architecture.technology_stack:
        gaps.append("Technology stack with justification is missing.")

    if not architecture.interface_contracts and len(architecture.components) > 1:
        gaps.append("Interface/API contracts between components are not defined.")

    if not architecture.ascii_diagram or len(architecture.ascii_diagram.strip()) < 10:
        gaps.append("ASCII architecture diagram is missing or too minimal.")

    if not architecture.adrs:
        gaps.append("At least one Architecture Decision Record (ADR) is expected.")

    if requirements:
        # Functional: user stories should be reflected in components/overview
        overview_and_resp = (
            architecture.system_overview.lower()
            + " "
            + " ".join(c.responsibilities.lower() for c in architecture.components)
        )
        for us in requirements.user_stories:
            ref = f"user story '{us.i_want[:50]}...'" if len(us.i_want) > 50 else f"user story '{us.i_want}'"
            if us.i_want.lower() not in overview_and_resp and us.as_a.lower() not in overview_and_resp:
                gaps.append(f"Functional requirement not clearly addressed: {ref}")

        # Non-functional: NFRs should be addressed in stack, ADRs, or deployment
        nfr_text = " ".join(
            nfr.description.lower() for nfr in requirements.non_functional_requirements
        )
        adr_and_topology = " ".join(
            a.context.lower() + a.decision.lower() + a.consequences.lower()
            for a in architecture.adrs
        ) + " " + architecture.deployment_topology.lower()
        stack_text = " ".join(
            t.justification.lower() for t in architecture.technology_stack
        )
        combined = adr_and_topology + " " + stack_text
        for nfr in requirements.non_functional_requirements:
            # Check if NFR category or key terms appear in architecture
            category = nfr.category.lower()
            desc = nfr.description.lower()
            if category not in combined and not any(
                word in combined for word in desc.split() if len(word) > 4
            ):
                gaps.append(
                    f"Non-functional requirement may not be addressed: [{nfr.category}] {nfr.description[:60]}..."
                )

    is_valid = len(gaps) == 0
    if not is_valid:
        logger.warning(
            "architecture_validation_gaps",
            gaps=gaps,
            has_requirements=requirements is not None,
        )
    return is_valid, gaps


def create_architect_agent(
    tools: Optional[List] = None,
    **kwargs,
) -> BaseAgent:
    """
    Create the Architect agent from config/agents.yaml with architect-specific tools.

    Uses role_name 'architect' (allow_delegation: true so the agent can consult
    DevOps/Cloud agents). Tools: architecture_designer, technology_selector,
    interface_definer, diagram_generator. Output should conform to
    ArchitectureDocument. Call validate_architecture_against_requirements after
    the agent produces an architecture to enforce the guardrail.
    """
    agent_tools = tools if tools is not None else get_architect_tools()
    return create_agent("architect", tools=agent_tools, **kwargs)
