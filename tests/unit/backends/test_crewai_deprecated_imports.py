"""Deprecated CrewAI import paths warn and still resolve (R10.3 / task 6.3)."""

from __future__ import annotations

import importlib
import sys

import pytest
from ai_team.backends.crewai_backend.agents.base import BaseAgent as NewBaseAgent
from ai_team.backends.crewai_backend.flows.main_flow import AITeamFlow as NewAITeamFlow


def _purge(prefix: str) -> None:
    for key in [k for k in sys.modules if k == prefix or k.startswith(prefix + ".")]:
        del sys.modules[key]


def test_agents_base_shim_warns_and_reexports() -> None:
    _purge("ai_team.agents")
    with pytest.warns(DeprecationWarning, match="crewai_backend.agents.base"):
        mod = importlib.import_module("ai_team.agents.base")
    assert mod.BaseAgent is NewBaseAgent


def test_crews_planning_shim_warns() -> None:
    _purge("ai_team.crews")
    with pytest.warns(DeprecationWarning, match="crewai_backend.crews.planning_crew"):
        mod = importlib.import_module("ai_team.crews.planning_crew")
    assert callable(mod.create_planning_crew)


def test_tasks_planning_shim_warns() -> None:
    _purge("ai_team.tasks")
    with pytest.warns(DeprecationWarning, match="crewai_backend.tasks.planning_tasks"):
        mod = importlib.import_module("ai_team.tasks.planning_tasks")
    assert callable(mod.create_planning_tasks)


def test_flows_main_flow_shim_warns_and_reexports() -> None:
    _purge("ai_team.flows")
    with pytest.warns(DeprecationWarning, match="crewai_backend.flows.main_flow"):
        mod = importlib.import_module("ai_team.flows.main_flow")
    assert mod.AITeamFlow is NewAITeamFlow
