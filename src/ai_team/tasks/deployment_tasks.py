"""
Deployment-phase tasks: infrastructure design, deployment packaging, documentation.

Dependency chain: infrastructure_design depends on architecture_design and
devops_configuration; deployment_packaging depends on infrastructure_design and
test_execution; documentation_generation depends on all previous tasks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Tuple

from crewai import Task

from ai_team.guardrails import crewai_code_safety_guardrail, crewai_iac_security_guardrail

if TYPE_CHECKING:
    from crewai import Agent


def _task_output_text(result: Any) -> str:
    """Extract raw text from CrewAI TaskOutput or similar."""
    if hasattr(result, "raw"):
        return getattr(result, "raw") or ""
    if isinstance(result, str):
        return result
    return str(result)


def _deployment_package_guardrail(result: Any) -> Tuple[bool, Any]:
    """CrewAI guardrail: deployment must include health checks and rollback strategy."""
    text = _task_output_text(result).lower()
    has_health = (
        "health" in text
        and ("check" in text or "liveness" in text or "readiness" in text or "probe" in text)
    )
    has_rollback = "rollback" in text or "roll back" in text or "revert" in text
    if not has_health:
        return (False, "Deployment must include health checks (e.g. liveness/readiness).")
    if not has_rollback:
        return (False, "Deployment must include a rollback strategy.")
    return (True, result)


def _documentation_content_guardrail(result: Any) -> Tuple[bool, Any]:
    """CrewAI guardrail: documentation must cover installation, usage, API reference."""
    text = _task_output_text(result).lower()
    checks = [
        ("installation" in text or "install" in text or "setup" in text, "installation/setup"),
        ("usage" in text or "how to use" in text or "getting started" in text, "usage"),
        ("api" in text or "reference" in text or "endpoint" in text, "API reference"),
    ]
    missing = [label for ok, label in checks if not ok]
    if missing:
        return (False, f"Documentation must cover: {', '.join(missing)}.")
    return (True, result)


def create_infrastructure_design_task(
    agent: "Agent",
    context: List[Task],
) -> Task:
    """
    Create the infrastructure_design task: design cloud infrastructure for the application.

    Depends on: architecture_design, devops_configuration.
    Guardrail: IaC must follow security best practices, least privilege.
    """
    return Task(
        name="infrastructure_design",
        description="Design cloud infrastructure for the application",
        agent=agent,
        context=context,
        expected_output="IaC templates (Terraform/CloudFormation)",
        guardrails=[crewai_code_safety_guardrail, crewai_iac_security_guardrail],
    )


def create_deployment_packaging_task(
    agent: "Agent",
    context: List[Task],
) -> Task:
    """
    Create the deployment_packaging task: package application for deployment with all configs.

    Depends on: infrastructure_design, test_execution.
    Guardrail: deployment must include health checks, rollback strategy.
    """
    return Task(
        name="deployment_packaging",
        description="Package application for deployment with all configs",
        agent=agent,
        context=context,
        expected_output="Complete deployment package with README",
        guardrails=[crewai_code_safety_guardrail, _deployment_package_guardrail],
    )


def create_documentation_generation_task(
    agent: "Agent",
    context: List[Task],
) -> Task:
    """
    Create the documentation_generation task: generate comprehensive project documentation.

    Product owner produces docs with architect context (via context tasks).
    Depends on: all previous tasks.
    Guardrail: documentation must cover installation, usage, API reference.
    """
    return Task(
        name="documentation_generation",
        description="Generate comprehensive project documentation",
        agent=agent,
        context=context,
        expected_output="README.md, API docs, setup guide, architecture docs",
        guardrails=[_documentation_content_guardrail],
    )
