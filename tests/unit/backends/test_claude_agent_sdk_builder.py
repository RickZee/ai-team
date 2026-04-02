"""Unit tests for Claude Agent SDK agent builder."""

from __future__ import annotations

from ai_team.backends.claude_agent_sdk_backend.agents.builder import (
    build_agent_definitions,
    orchestrator_system_prompt,
)
from ai_team.core.team_profile import TeamProfile


def test_build_agent_definitions_full_profile() -> None:
    """Full profile includes planning, development, testing, deployment agents."""
    profile = TeamProfile(
        name="full",
        agents=[
            "manager",
            "product_owner",
            "architect",
            "backend_developer",
            "frontend_developer",
            "qa_engineer",
            "devops_engineer",
            "cloud_engineer",
        ],
        phases=["intake", "planning", "development", "testing", "deployment"],
    )
    agents = build_agent_definitions(profile)
    assert "planning-agent" in agents
    assert "development-agent" in agents
    assert "testing-agent" in agents
    assert "deployment-agent" in agents
    assert "product-owner" in agents
    assert "architect" in agents


def test_model_override_applied() -> None:
    """Profile model_overrides change AgentDefinition.model for a role."""
    profile = TeamProfile(
        name="t",
        agents=["product_owner", "architect"],
        phases=["planning"],
        model_overrides={"architect": "sonnet"},
    )
    agents = build_agent_definitions(profile)
    assert agents["architect"].model == "sonnet"


def test_backend_api_profile_excludes_frontend_agent() -> None:
    """backend-api profile has no frontend developer; development-agent still builds."""
    profile = TeamProfile(
        name="backend-api",
        agents=[
            "manager",
            "product_owner",
            "architect",
            "backend_developer",
            "qa_engineer",
            "devops_engineer",
        ],
        phases=["intake", "planning", "development", "testing", "deployment"],
    )
    agents = build_agent_definitions(profile)
    assert "frontend-developer" not in agents
    assert "backend-developer" in agents


def test_product_owner_disallowed_tools_defense_in_depth() -> None:
    profile = TeamProfile(
        name="t",
        agents=["product_owner"],
        phases=["planning"],
    )
    agents = build_agent_definitions(profile)
    po = agents["product-owner"]
    assert po.disallowedTools is not None
    assert "Bash" in po.disallowedTools


def test_orchestrator_system_prompt_includes_profile_name() -> None:
    profile = TeamProfile(
        name="proto",
        agents=["architect"],
        phases=["planning"],
    )
    text = orchestrator_system_prompt(profile, max_retries=2)
    assert "proto" in text
    assert "max 2 retries" in text
