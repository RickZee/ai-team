"""Cheap vs strong verification split (R8). Cheap path never loads the planner."""

from __future__ import annotations

from typing import Literal

from ai_team.harness.router import DETERMINISTIC_SENTINEL, resolve_route

VerifierKind = Literal["cheap", "strong"]

CHEAP_TASK_TYPE = "mechanical_check"
STRONG_TASK_TYPE = "judge"


def verifier_route(kind: VerifierKind, env: str = "dev") -> str:
    """Return the model id (or ``deterministic``) for a verifier kind."""
    task = CHEAP_TASK_TYPE if kind == "cheap" else STRONG_TASK_TYPE
    route = resolve_route(task, env)
    return route.model_id


def cheap_path_is_deterministic(env: str = "dev") -> bool:
    """True when cheap verification will not instantiate a planning model."""
    route = resolve_route(CHEAP_TASK_TYPE, env)
    return route.deterministic or route.model_id == DETERMINISTIC_SENTINEL
