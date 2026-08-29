"""Task-typed routing table."""

from __future__ import annotations

from ai_team.harness.router import DETERMINISTIC_SENTINEL, resolve_route
from ai_team.harness.verifiers import cheap_path_is_deterministic, verifier_route


def test_mechanical_check_is_deterministic() -> None:
    route = resolve_route("mechanical_check", "dev")
    assert route.deterministic is True
    assert route.model_id == DETERMINISTIC_SENTINEL


def test_missing_type_falls_back_generate() -> None:
    table = {"routes": {"dev": {"generate": "openrouter/anthropic/claude-sonnet-4.6"}}}
    route = resolve_route("classify", "dev", routes=table)
    assert route.unwired is True
    assert route.model_id == "openrouter/anthropic/claude-sonnet-4.6"


def test_same_model_override() -> None:
    route = resolve_route(
        "generate",
        "dev",
        same_model=True,
        same_model_id="openrouter/openai/gpt-4.1-mini",
    )
    assert route.same_model is True
    assert route.model_id == "openrouter/openai/gpt-4.1-mini"
    mech = resolve_route(
        "mechanical_check",
        "dev",
        same_model=True,
        same_model_id="openrouter/openai/gpt-4.1-mini",
    )
    assert mech.deterministic is True
    assert mech.model_id == DETERMINISTIC_SENTINEL


def test_cheap_verifier_not_architect_model() -> None:
    assert cheap_path_is_deterministic("dev") is True
    assert verifier_route("cheap", "dev") == DETERMINISTIC_SENTINEL
    plan = resolve_route("plan", "dev")
    assert plan.model_id != DETERMINISTIC_SENTINEL
    assert verifier_route("cheap", "dev") != plan.model_id
