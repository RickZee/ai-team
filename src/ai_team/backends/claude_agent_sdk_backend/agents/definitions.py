"""Concrete :class:`AgentDefinition` instances for specialists and phase coordinators."""

from __future__ import annotations

from ai_team.backends.claude_agent_sdk_backend.agents import prompts
from ai_team.backends.claude_agent_sdk_backend.tools.permissions import (
    architect_allowed_tools,
    developer_allowed_tools,
    devops_allowed_tools,
    orchestrator_allowed_tools,
    planning_allowed_tools,
    qa_allowed_tools,
    specialist_writer_tools,
)
from claude_agent_sdk import AgentDefinition


def make_product_owner(*, model: str, effort: str | None = "medium") -> AgentDefinition:
    return AgentDefinition(
        description="Requirements analyst: user stories, acceptance criteria, MoSCoW prioritization.",
        prompt=prompts.product_owner_prompt(),
        tools=specialist_writer_tools(),
        model=model,
        effort=effort,
    )


def make_architect(*, model: str, effort: str | None = "high") -> AgentDefinition:
    return AgentDefinition(
        description="Solutions architect: system design, ADRs, technical stack.",
        prompt=prompts.architect_prompt(),
        tools=architect_allowed_tools(),
        model=model,
        effort=effort,
    )


def make_planning_agent(
    *,
    model: str,
    available_label: str,
    effort: str | None = "medium",
) -> AgentDefinition:
    return AgentDefinition(
        description="Coordinates requirements and architecture documents.",
        prompt=prompts.planning_coordinator_prompt(available_label),
        tools=planning_allowed_tools(include_mcp=True),
        model=model,
        effort=effort,
    )


def make_backend_developer(*, model: str, effort: str | None = "high") -> AgentDefinition:
    return AgentDefinition(
        description="Backend developer for APIs, services, persistence.",
        prompt=prompts.backend_developer_prompt(),
        tools=developer_allowed_tools(),
        model=model,
        effort=effort,
    )


def make_frontend_developer(*, model: str, effort: str | None = "medium") -> AgentDefinition:
    return AgentDefinition(
        description="Frontend developer for UI components and client code.",
        prompt=prompts.frontend_developer_prompt(),
        tools=developer_allowed_tools(),
        model=model,
        effort=effort,
    )


def make_fullstack_developer(*, model: str, effort: str | None = "high") -> AgentDefinition:
    return AgentDefinition(
        description="Fullstack developer for combined client and server work.",
        prompt=prompts.fullstack_developer_prompt(),
        tools=developer_allowed_tools(),
        model=model,
        effort=effort,
    )


def make_development_agent(
    *,
    model: str,
    available_label: str,
    effort: str | None = "medium",
) -> AgentDefinition:
    return AgentDefinition(
        description="Coordinates implementation across developer specialists.",
        prompt=prompts.development_coordinator_prompt(available_label),
        tools=planning_allowed_tools(include_mcp=True) + ["Edit"],
        model=model,
        effort=effort,
    )


def make_testing_agent(*, model: str, effort: str | None = "medium") -> AgentDefinition:
    return AgentDefinition(
        description="QA: tests, execution, structured reports.",
        prompt=prompts.testing_agent_prompt(),
        tools=qa_allowed_tools(),
        model=model,
        effort=effort,
    )


def make_devops_engineer(*, model: str, effort: str | None = "low") -> AgentDefinition:
    return AgentDefinition(
        description="DevOps: containers, CI workflows, operational glue.",
        prompt=prompts.devops_prompt(),
        tools=devops_allowed_tools(),
        model=model,
        effort=effort,
    )


def make_cloud_engineer(*, model: str, effort: str | None = "low") -> AgentDefinition:
    return AgentDefinition(
        description="Cloud / IaC engineer.",
        prompt=prompts.cloud_prompt(),
        tools=devops_allowed_tools(),
        model=model,
        effort=effort,
    )


def make_deployment_agent(
    *,
    model: str,
    available_label: str,
    effort: str | None = "medium",
) -> AgentDefinition:
    return AgentDefinition(
        description="Coordinates DevOps and cloud specialists.",
        prompt=prompts.deployment_coordinator_prompt(available_label),
        tools=planning_allowed_tools(include_mcp=True),
        model=model,
        effort=effort,
    )


def default_orchestrator_allowed_tools(*, include_skill: bool = False) -> list[str]:
    """Tools for the top-level orchestrator query."""
    base = orchestrator_allowed_tools()
    if include_skill:
        return base + ["Skill"]
    return base
