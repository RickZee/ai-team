"""TypedDict state schemas for the LangGraph main graph and subgraphs."""

from __future__ import annotations

import operator
from typing import Annotated, Any, NotRequired, TypedDict

from langgraph.graph.message import add_messages
from langgraph.managed import RemainingSteps


def reset_or_extend_errors(
    left: list[dict[str, Any]], right: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Reducer for ``errors``: an empty update clears the list, else appends.

    Phase nodes return ``"errors": []`` after recovering (e.g. development
    re-runs cleanly on retry) to signal "this phase is now healthy". Plain
    ``operator.add`` would make that a no-op append, so a stale error from a
    prior failed attempt would persist and force terminal routing. Treating an
    empty right-hand update as a reset lets the retry loop recover, while a
    non-empty update accumulates as before.
    """
    if not right:
        return []
    return list(left) + list(right)


class LangGraphProjectState(TypedDict, total=False):
    """Top-level state flowing through the main LangGraph (migration plan §3.1)."""

    project_description: str
    project_id: str
    current_phase: str
    phase_history: Annotated[list[dict[str, Any]], operator.add]
    requirements: dict[str, Any] | None
    architecture: dict[str, Any] | None
    generated_files: Annotated[list[dict[str, Any]], operator.add]
    test_results: dict[str, Any] | None
    deployment_config: dict[str, Any] | None
    errors: Annotated[list[dict[str, Any]], reset_or_extend_errors]
    retry_count: int
    max_retries: int
    human_feedback: str | None
    messages: Annotated[list[Any], add_messages]
    metadata: NotRequired[dict[str, Any]]


class PlanningState(TypedDict, total=False):
    """Internal planning subgraph state (migration plan §3.2)."""

    project_description: str
    messages: Annotated[list[Any], add_messages]
    requirements: dict[str, Any] | None
    architecture: dict[str, Any] | None
    current_agent: str


class DevelopmentState(TypedDict, total=False):
    """Internal development subgraph state."""

    requirements: dict[str, Any]
    architecture: dict[str, Any]
    messages: Annotated[list[Any], add_messages]
    generated_files: Annotated[list[dict[str, Any]], operator.add]
    current_agent: str


class TestingState(TypedDict, total=False):
    """Internal testing subgraph state."""

    generated_files: list[dict[str, Any]]
    messages: Annotated[list[Any], add_messages]
    test_results: dict[str, Any] | None


class DeploymentState(TypedDict, total=False):
    """Internal deployment subgraph state."""

    generated_files: list[dict[str, Any]]
    architecture: dict[str, Any] | None
    messages: Annotated[list[Any], add_messages]
    deployment_config: dict[str, Any] | None


class LangGraphSubgraphState(TypedDict):
    """
    Shared state for Phase-3 subgraphs wrapped with guardrail nodes (Phase 5).

    ``guardrail_checks`` accumulates per-phase results; ``guardrail_retry_count`` tracks
    retries after failed checks (capped in routing).
    """

    messages: Annotated[list[Any], add_messages]
    remaining_steps: NotRequired[RemainingSteps]
    guardrail_checks: Annotated[list[dict[str, Any]], operator.add]
    project_description: NotRequired[str]
    requirements: NotRequired[dict[str, Any]]
    architecture: NotRequired[dict[str, Any]]
    generated_files: NotRequired[list[dict[str, Any]]]
    guardrail_retry_count: NotRequired[int]
    guardrail_terminal: NotRequired[bool]
