"""Unit tests for LangGraph routing functions (no LLM)."""

from __future__ import annotations

from ai_team.backends.langgraph_backend.graphs.routing import (
    normalize_hitl_metadata,
    route_after_deployment,
    route_after_development,
    route_after_human_review,
    route_after_intake,
    route_after_planning,
    route_after_testing,
)


def test_route_after_intake_valid() -> None:
    state = {"project_description": "x" * 20, "errors": []}
    assert route_after_intake(state) == "planning"


def test_route_after_intake_too_short() -> None:
    state = {"project_description": "short", "errors": []}
    assert route_after_intake(state) == "error"


def test_route_after_intake_has_errors() -> None:
    state = {"project_description": "x" * 20, "errors": [{"msg": "x"}]}
    assert route_after_intake(state) == "error"


def test_route_after_planning_errors() -> None:
    state = {"errors": [{"x": 1}]}
    assert route_after_planning(state) == "error"


def test_route_after_planning_human() -> None:
    state = {"errors": [], "metadata": {"planning_needs_human": True}}
    assert route_after_planning(state) == "human_review"


def test_route_after_planning_development() -> None:
    state = {"errors": [], "metadata": {}}
    assert route_after_planning(state) == "development"


def test_route_after_development() -> None:
    assert route_after_development({"errors": []}) == "testing"
    assert route_after_development({"errors": [{"e": 1}]}) == "error"


def test_route_after_testing_passed() -> None:
    state = {"errors": [], "test_results": {"passed": True}}
    assert route_after_testing(state) == "deployment"


def test_route_after_testing_retry() -> None:
    state = {
        "errors": [],
        "test_results": {"passed": False},
        "retry_count": 0,
        "max_retries": 3,
    }
    assert route_after_testing(state) == "retry_development"


def test_route_after_testing_exhausted_to_human() -> None:
    state = {
        "errors": [],
        "test_results": {"passed": False},
        "retry_count": 3,
        "max_retries": 3,
    }
    assert route_after_testing(state) == "human_review"


def test_route_after_testing_needs_human_flag() -> None:
    state = {"errors": [], "metadata": {"testing_needs_human": True}}
    assert route_after_testing(state) == "human_review"


def test_route_after_deployment() -> None:
    assert route_after_deployment({"errors": []}) == "complete"
    assert route_after_deployment({"errors": [{"e": 1}]}) == "error"


def test_route_after_human_review_planning() -> None:
    state = {"metadata": {"hitl_source": "planning"}}
    assert route_after_human_review(state) == "development"


def test_route_after_human_review_testing() -> None:
    state = {"metadata": {"hitl_source": "testing"}}
    assert route_after_human_review(state) == "retry_development"


def test_normalize_hitl_metadata_explicit() -> None:
    assert (
        normalize_hitl_metadata({"metadata": {"hitl_source": "planning"}})[
            "hitl_source"
        ]
        == "planning"
    )


def test_normalize_hitl_metadata_from_planning_flag() -> None:
    m = normalize_hitl_metadata({"metadata": {"planning_needs_human": True}})
    assert m.get("hitl_source") == "planning"


def test_normalize_hitl_metadata_from_failed_tests() -> None:
    m = normalize_hitl_metadata({"metadata": {}, "test_results": {"passed": False}})
    assert m.get("hitl_source") == "testing"
