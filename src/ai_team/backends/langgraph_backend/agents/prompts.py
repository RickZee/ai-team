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

    def system_message(self, *, lessons: list[str] | None = None) -> str:
        """Single system prompt for ReAct / chat models (optionally with learned lessons)."""
        base = (
            f"You are {self.role}.\n\n"
            f"## Goal\n{self.goal.strip()}\n\n"
            f"## Background\n{self.backstory.strip()}\n"
        )
        lesson_lines = [
            lesson.strip()
            for lesson in (lessons or [])
            if isinstance(lesson, str) and lesson.strip()
        ]
        if not lesson_lines:
            return base
        bullets = "\n".join([f"- {t}" for t in lesson_lines[:20]])
        return base + "\n\n" + "## Lessons from previous runs\n" + bullets + "\n"


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


def build_system_prompt(role_key: str) -> str:
    """
    Build the full system prompt for a role, including promoted lessons (if any).

    Lessons are persisted in the long-term SQLite store and loaded at runtime.
    Failures to load lessons must never break prompt generation.
    """
    bundle = load_agent_prompt(role_key)
    try:
        from ai_team.memory.lessons import load_role_lessons

        role_lessons = load_role_lessons(agent_role=role_key)
        return bundle.system_message(lessons=[lsn.text for lsn in role_lessons])
    except Exception:
        return bundle.system_message()


def list_agent_role_keys() -> list[str]:
    """Return all top-level agent keys from ``agents.yaml``."""
    return sorted(load_agents_yaml().keys())
