"""Pure conditional-edge functions for the LangGraph main graph (Phase 1 skeleton)."""

from __future__ import annotations

from typing import Any, Literal

from ai_team.backends.langgraph_backend.graphs.state import LangGraphProjectState

MIN_PROJECT_DESCRIPTION_LENGTH = 10


def normalize_hitl_metadata(state: LangGraphProjectState) -> dict[str, Any]:
    """
    Ensure ``metadata.hitl_source`` is set before ``human_review`` routing.

    Planning vs testing escalation is inferred from flags and test results when unset.
    """
    meta = dict(state.get("metadata") or {})
    if meta.get("hitl_source"):
        return meta
    if meta.get("planning_needs_human"):
        meta["hitl_source"] = "planning"
    elif meta.get("testing_needs_human"):
        meta["hitl_source"] = "testing"
    else:
        tr = state.get("test_results") or {}
        if tr.get("passed") is False:
            meta["hitl_source"] = "testing"
    return meta


def route_after_intake(state: LangGraphProjectState) -> Literal["planning", "error"]:
    """Route after intake: valid description → planning; otherwise error."""
    desc = (state.get("project_description") or "").strip()
    if len(desc) < MIN_PROJECT_DESCRIPTION_LENGTH:
        return "error"
    errs = state.get("errors") or []
    if errs:
        return "error"
    return "planning"


def route_after_planning(
    state: LangGraphProjectState,
) -> Literal["development", "human_review", "error"]:
    """Route after planning: development, human review, or error."""
    errs = state.get("errors") or []
    if errs:
        return "error"
    meta = state.get("metadata") or {}
    if meta.get("planning_needs_human"):
        return "human_review"
    return "development"


def route_after_development(
    state: LangGraphProjectState,
) -> Literal["testing", "error"]:
    """Route after development: testing or error."""
    errs = state.get("errors") or []
    if errs:
        return "error"
    return "testing"


def route_after_testing(
    state: LangGraphProjectState,
) -> Literal["deployment", "retry_development", "human_review", "error"]:
    """Route after testing: deployment, retry development, human escalation, or error."""
    errs = state.get("errors") or []
    if errs:
        return "error"
    meta = state.get("metadata") or {}
    if meta.get("testing_needs_human"):
        return "human_review"
    tr = state.get("test_results") or {}
    passed = tr.get("passed", True)
    if not passed:
        rc = int(state.get("retry_count") or 0)
        mx = int(state.get("max_retries") or 3)
        if rc < mx:
            return "retry_development"
        return "human_review"
    return "deployment"


def route_after_deployment(
    state: LangGraphProjectState,
) -> Literal["complete", "error"]:
    """Route after deployment: complete or terminal error."""
    errs = state.get("errors") or []
    if errs:
        return "error"
    return "complete"


def route_after_human_review(
    state: LangGraphProjectState,
) -> Literal["development", "retry_development"]:
    """
    After human review: planning approval → development; testing escalation → retry dev.

    Expects ``metadata.hitl_source`` (set by ``normalize_hitl_metadata`` in the node).
    """
    meta = state.get("metadata") or {}
    if meta.get("hitl_source") == "testing":
        return "retry_development"
    return "development"
