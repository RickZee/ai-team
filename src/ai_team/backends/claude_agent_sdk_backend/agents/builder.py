"""Build ``agents`` map for :class:`ClaudeAgentOptions` from :class:`TeamProfile`."""

from __future__ import annotations

import dataclasses
from typing import Literal

from ai_team.backends.claude_agent_sdk_backend.agents import definitions as defs
from ai_team.backends.claude_agent_sdk_backend.agents import prompts
from ai_team.backends.claude_agent_sdk_backend.tools.permissions import (
    get_disallowed_tools_for_yaml_role,
)
from ai_team.core.team_profile import TeamProfile
from claude_agent_sdk import AgentDefinition

Effort = Literal["low", "medium", "high", "max"]


def _with_disallowed(role: str, agent_def: AgentDefinition) -> AgentDefinition:
    banned = get_disallowed_tools_for_yaml_role(role)
    if not banned:
        return agent_def
    return dataclasses.replace(agent_def, disallowedTools=banned)


def _effort(profile: TeamProfile, role: str, default: Effort) -> Effort:
    raw = profile.metadata.get("claude_agent_sdk") or {}
    efforts = raw.get("effort") if isinstance(raw, dict) else {}
    if isinstance(efforts, dict):
        v = efforts.get(role)
        if v in ("low", "medium", "high", "max"):
            return v
    return default


def _model(profile: TeamProfile, role: str, default: str) -> str:
    v = profile.model_overrides.get(role)
    if isinstance(v, str) and v.strip():
        return v.strip()
    return default


def _has(profile: TeamProfile, role: str) -> bool:
    return role in profile.agents


def build_agent_definitions(profile: TeamProfile) -> dict[str, AgentDefinition]:
    """
    Return phase agents plus specialists registered for this profile.

    Keys match Agent-tool subagent names (hyphenated). The orchestrator should
    only delegate to keys present in this dict.
    """
    out: dict[str, AgentDefinition] = {}

    spec_labels: list[str] = []
    if _has(profile, "product_owner"):
        spec_labels.append("product-owner")
        out["product-owner"] = _with_disallowed(
            "product_owner",
            defs.make_product_owner(
                model=_model(profile, "product_owner", "sonnet"),
                effort=_effort(profile, "product_owner", "medium"),
            ),
        )
    if _has(profile, "architect"):
        spec_labels.append("architect")
        out["architect"] = _with_disallowed(
            "architect",
            defs.make_architect(
                model=_model(profile, "architect", "opus"),
                effort=_effort(profile, "architect", "high"),
            ),
        )

    dev_labels: list[str] = []
    if _has(profile, "backend_developer"):
        dev_labels.append("backend-developer")
        out["backend-developer"] = _with_disallowed(
            "backend_developer",
            defs.make_backend_developer(
                model=_model(profile, "backend_developer", "sonnet"),
                effort=_effort(profile, "backend_developer", "high"),
            ),
        )
    if _has(profile, "frontend_developer"):
        dev_labels.append("frontend-developer")
        out["frontend-developer"] = _with_disallowed(
            "frontend_developer",
            defs.make_frontend_developer(
                model=_model(profile, "frontend_developer", "sonnet"),
                effort=_effort(profile, "frontend_developer", "medium"),
            ),
        )
    if _has(profile, "fullstack_developer"):
        dev_labels.append("fullstack-developer")
        out["fullstack-developer"] = _with_disallowed(
            "fullstack_developer",
            defs.make_fullstack_developer(
                model=_model(profile, "fullstack_developer", "sonnet"),
                effort=_effort(profile, "fullstack_developer", "high"),
            ),
        )

    dep_labels: list[str] = []
    if _has(profile, "devops_engineer"):
        dep_labels.append("devops-engineer")
        out["devops-engineer"] = _with_disallowed(
            "devops_engineer",
            defs.make_devops_engineer(
                model=_model(profile, "devops_engineer", "haiku"),
                effort=_effort(profile, "devops_engineer", "low"),
            ),
        )
    if _has(profile, "cloud_engineer"):
        dep_labels.append("cloud-engineer")
        out["cloud-engineer"] = _with_disallowed(
            "cloud_engineer",
            defs.make_cloud_engineer(
                model=_model(profile, "cloud_engineer", "haiku"),
                effort=_effort(profile, "cloud_engineer", "low"),
            ),
        )

    phases = {p.strip().lower() for p in profile.phases}

    if "planning" in phases and spec_labels:
        out["planning-agent"] = _with_disallowed(
            "manager",
            defs.make_planning_agent(
                model=_model(profile, "manager", "sonnet"),
                available_label=", ".join(spec_labels),
                effort=_effort(profile, "manager", "medium"),
            ),
        )

    if "development" in phases and dev_labels:
        out["development-agent"] = _with_disallowed(
            "manager",
            defs.make_development_agent(
                model=_model(profile, "manager", "sonnet"),
                available_label=", ".join(dev_labels),
                effort=_effort(profile, "manager", "medium"),
            ),
        )

    if "testing" in phases and _has(profile, "qa_engineer"):
        out["testing-agent"] = _with_disallowed(
            "qa_engineer",
            defs.make_testing_agent(
                model=_model(profile, "qa_engineer", "sonnet"),
                effort=_effort(profile, "qa_engineer", "medium"),
            ),
        )

    if "deployment" in phases and dep_labels:
        out["deployment-agent"] = _with_disallowed(
            "manager",
            defs.make_deployment_agent(
                model=_model(profile, "manager", "sonnet"),
                available_label=", ".join(dep_labels),
                effort=_effort(profile, "manager", "medium"),
            ),
        )

    return out


def orchestrator_system_prompt(profile: TeamProfile, *, max_retries: int = 3) -> str:
    """System prompt for the top-level orchestrator ``query()`` call."""
    return prompts.orchestrator_prompt(
        profile_name=profile.name,
        agent_list=", ".join(profile.agents),
        phase_list=", ".join(profile.phases),
        max_retries=max_retries,
    )


def orchestrator_user_prompt(description: str) -> str:
    """User message body (project description) for the main ``query()`` call."""
    return (
        f"## Project description\n\n{description.strip()}\n\n"
        "Inspect workspace/docs/project_brief.md, then execute the phased plan using "
        "the Agent tool for each phase agent that is available."
    )
