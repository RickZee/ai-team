"""
System prompts for LangGraph agents, sourced from ``config/agents.yaml``.

Same role/goal/backstory as CrewAI so both backends stay aligned.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

_CONFIG_NAME = "agents.yaml"


def _agents_yaml_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent / "config" / _CONFIG_NAME


def load_agents_yaml() -> dict[str, Any]:
    """Load raw agent definitions from ``config/agents.yaml``."""
    path = _agents_yaml_path()
    if not path.exists():
        logger.error("agents_yaml_missing", path=str(path))
        raise FileNotFoundError(f"Agents config not found: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class AgentPromptBundle(BaseModel):
    """Structured prompt fields for one agent role."""

    role_key: str = Field(..., description="YAML key, e.g. manager, qa_engineer.")
    role: str = Field(..., description="Human-readable role title.")
    goal: str = Field(..., description="What the agent optimizes for.")
    backstory: str = Field(..., description="Persona and behavioral constraints.")

    def system_message(self) -> str:
        """Single system prompt for ReAct / chat models."""
        return (
            f"You are {self.role}.\n\n"
            f"## Goal\n{self.goal.strip()}\n\n"
            f"## Background\n{self.backstory.strip()}\n"
        )


def load_agent_prompt(role_key: str) -> AgentPromptBundle:
    """Load prompt fields for ``role_key`` (must exist in ``agents.yaml``)."""
    data = load_agents_yaml()
    if role_key not in data:
        available = ", ".join(sorted(data.keys()))
        raise KeyError(f"Unknown agent role {role_key!r}. Known: {available}")
    block = data[role_key]
    if not isinstance(block, dict):
        raise ValueError(f"Invalid agents.yaml entry for {role_key!r}")
    return AgentPromptBundle(
        role_key=role_key,
        role=str(block.get("role", role_key)),
        goal=str(block.get("goal", "")),
        backstory=str(block.get("backstory", "")),
    )


def list_agent_role_keys() -> list[str]:
    """Return all top-level agent keys from ``agents.yaml``."""
    return sorted(load_agents_yaml().keys())
