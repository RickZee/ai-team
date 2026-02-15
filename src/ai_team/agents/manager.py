"""Manager agent — coordinates the team, delegates work, and escalates when needed."""

from pathlib import Path
from typing import Any

import yaml
from crewai import Agent, LLM

from ai_team.config.settings import get_settings
from ai_team.tools.manager_tools import get_manager_tools


def _load_agents_config() -> dict:
    """Load agents.yaml from config. Returns raw dict; manager key may be missing."""
    config_path = Path(__file__).resolve().parent.parent / "config" / "agents.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def _get_manager_config() -> dict:
    """Get Manager agent config from YAML with defaults."""
    data = _load_agents_config()
    raw = data.get("manager") or {}
    return {
        "role": raw.get("role", "Engineering Manager"),
        "goal": raw.get(
            "goal",
            "Coordinate the team, resolve blockers, and ensure on-time delivery. "
            "Delegate tasks to the right agents and escalate to humans when needed.",
        ),
        "backstory": raw.get(
            "backstory",
            "You are a seasoned engineering leader with over 20 years of experience. "
            "You delegate with clarity, track timelines, and escalate when scope or risk require human input.",
        ),
        "allow_delegation": raw.get("allow_delegation", True),
        "model": raw.get("model"),
    }


def get_manager_agent(**kwargs: Any) -> Agent:
    """Return a configured Manager agent with delegation and human escalation support.

    Uses config/agents.yaml when present. The Manager has tools for task_delegation,
    timeline_management, and blocker_resolution. Set escalate_to_human=True in
    blocker_resolution to trigger human-in-the-loop; the flow can listen for
    AWAITING_HUMAN and resume after input.
    """
    settings = get_settings()
    config = _get_manager_config()
    model = config.get("model") or settings.ollama.get_model_for_role("manager")
    # CrewAI uses LiteLLM; use ollama/ prefix so the right provider is used
    model_id = model if model.startswith("ollama/") else f"ollama/{model}"

    llm = LLM(
        model=model_id,
        base_url=settings.ollama.base_url,
        temperature=settings.ollama.temperature,
        num_ctx=settings.ollama.num_ctx,
    )

    tools = get_manager_tools(**kwargs)

    return Agent(
        role=config["role"],
        goal=config["goal"],
        backstory=config["backstory"],
        tools=tools,
        llm=llm,
        allow_delegation=config["allow_delegation"],
        verbose=settings.crew_verbose,
        **kwargs,
    )
