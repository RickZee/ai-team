"""Backend Developer agent — implements services, APIs, and data layers with quality guardrails and self-review."""

from pathlib import Path
from typing import Any

import yaml
from crewai import Agent, LLM

from ai_team.config.settings import get_settings
from ai_team.tools.backend_developer_tools import get_backend_developer_tools


def _load_agents_config() -> dict:
    """Load agents.yaml from config."""
    config_path = Path(__file__).resolve().parent.parent / "config" / "agents.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def _get_backend_developer_config() -> dict:
    """Get Backend Developer agent config from YAML with defaults."""
    data = _load_agents_config()
    raw = data.get("backend_developer") or {}
    return {
        "role": raw.get("role", "Backend Developer"),
        "goal": raw.get(
            "goal",
            "Implement robust backend services, APIs, and data layers in Python, Node.js, or Go. "
            "Deliver production-ready code that passes quality guardrails and complete a self-review before marking any task done.",
        ),
        "backstory": raw.get(
            "backstory",
            "You are a senior backend engineer with experience in Python, Node.js, and Go. "
            "You design schemas, implement APIs, and run a self-review loop before completing tasks.",
        ),
        "allow_delegation": raw.get("allow_delegation", False),
        "model": raw.get("model"),
    }


def get_backend_developer_agent(**kwargs: Any) -> Agent:
    """Return a configured Backend Developer agent with code generation, DB schema, API tools, and guardrail integration.

    Uses config/agents.yaml when present. The agent has tools: code_generation,
    database_schema_design, api_implementation, code_quality_check, and self_review.
    Always run code_quality_check after generating code and self_review before marking a task complete.
    """
    settings = get_settings()
    config = _get_backend_developer_config()
    model = config.get("model") or settings.ollama.get_model_for_role("backend_developer")
    model_id = model if model.startswith("ollama/") else f"ollama/{model}"

    llm = LLM(
        model=model_id,
        base_url=settings.ollama.base_url,
        temperature=settings.ollama.temperature,
        num_ctx=settings.ollama.num_ctx,
    )

    tools = get_backend_developer_tools(**kwargs)

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
