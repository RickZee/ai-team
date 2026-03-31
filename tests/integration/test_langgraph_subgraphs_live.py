"""Integration: compile planning/development supervisors (requires OpenRouter + bind_tools)."""

from __future__ import annotations

import os

import pytest


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY required for supervisor LLM bind_tools",
)
def test_compile_planning_subgraph_live() -> None:
    """Supervisor + workers require a real chat model with ``bind_tools``."""
    from ai_team.backends.langgraph_backend.graphs.planning import (
        compile_planning_subgraph,
    )

    g = compile_planning_subgraph()
    assert g.get_graph().nodes


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY required for supervisor LLM bind_tools",
)
def test_compile_development_subgraph_live() -> None:
    from ai_team.backends.langgraph_backend.graphs.development import (
        compile_development_subgraph,
    )

    g = compile_development_subgraph()
    assert g.get_graph().nodes
