"""Pytest configuration and fixtures for unit tests."""

import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_ollama import ChatOllama

# CrewAI 0.80 has no crewai.agent.core; tests patch crewai.agent.core.create_llm.
# Inject a minimal shim so patch() can attach (Agent 0.80 does not call create_llm).
try:
    import crewai.agent as _crewai_agent
    if not hasattr(_crewai_agent, "core"):
        _crewai_agent.core = types.ModuleType("core")
        _crewai_agent.core.create_llm = lambda llm: llm
except Exception:
    pass


def _identity_llm(llm: object) -> object:
    """Pass-through so CrewAI uses our LLM as-is in tests."""
    return llm


@pytest.fixture
def mock_ollama_llm() -> ChatOllama:
    """Real ChatOllama instance; no network if not invoked."""
    return ChatOllama(model="qwen3:14b", base_url="http://localhost:11434")


@pytest.fixture
def agents_config_minimal() -> dict:
    """Minimal agents.yaml-style config for create_agent tests."""
    return {
        "manager": {
            "role": "Engineering Manager",
            "goal": "Coordinate the team.",
            "backstory": "Experienced leader.",
            "verbose": True,
            "allow_delegation": True,
            "max_iter": 15,
            "memory": True,
        },
        "product_owner": {
            "role": "Product Owner",
            "goal": "Define requirements.",
            "backstory": "Product expert.",
            "verbose": True,
            "allow_delegation": False,
            "max_iter": 10,
            "memory": True,
        },
        "architect": {
            "role": "Architect",
            "goal": "Design systems.",
            "backstory": "Architecture expert.",
            "verbose": True,
            "allow_delegation": True,
            "max_iter": 12,
            "memory": True,
        },
        "backend_developer": {
            "role": "Backend Developer",
            "goal": "Implement backend.",
            "backstory": "Backend expert.",
            "verbose": True,
            "allow_delegation": False,
            "max_iter": 15,
            "memory": True,
        },
        "qa_engineer": {
            "role": "QA Engineer",
            "goal": "Test and assure quality.",
            "backstory": "QA expert.",
            "verbose": True,
            "allow_delegation": False,
            "max_iter": 10,
            "memory": True,
        },
    }


@pytest.fixture
def sample_project_description() -> str:
    """Sample project description for flow/crew tests."""
    return (
        "Build a simple REST API for a todo list: CRUD endpoints, "
        "in-memory storage, and OpenAPI docs. Use Python and FastAPI."
    )


# Export for use in test modules that need the same patch pattern
identity_llm = _identity_llm
