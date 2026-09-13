"""Registry for CrewAI Flow introspection without evals importing ``flows``."""

from __future__ import annotations

from ai_team.backends.crewai_backend.flows.main_flow import AITeamFlow
from ai_team.core import flow_wiring
from ai_team.core.flow_wiring import get_registered_flow_class, self_triggering_listeners


def test_importing_main_flow_registers_ai_team_flow() -> None:
    assert get_registered_flow_class() is AITeamFlow


def test_self_triggering_listeners_empty_on_production_flow() -> None:
    assert self_triggering_listeners(AITeamFlow) == []


def test_unregistered_class_does_not_pin_empty_eval_cache() -> None:
    from evals.checks import trajectory

    saved_cls = flow_wiring._FLOW_CLS
    saved_cache = trajectory._SELF_TRIGGER_CACHE
    try:
        flow_wiring._FLOW_CLS = None
        trajectory._SELF_TRIGGER_CACHE = None
        assert trajectory._cached_self_triggering_listeners() == []
        assert trajectory._SELF_TRIGGER_CACHE is None
        flow_wiring.register_flow_class(AITeamFlow)
        assert trajectory._cached_self_triggering_listeners() == []
        cached = trajectory._SELF_TRIGGER_CACHE
        assert cached is not None
        assert len(cached) == 0
    finally:
        flow_wiring._FLOW_CLS = saved_cls
        trajectory._SELF_TRIGGER_CACHE = saved_cache
