"""Backwards-compatible re-export of the shared spend guard.

The spend guard moved to ``ai_team.core.spend_guard`` when it became
backend-agnostic (now also used by the CrewAI backend). This shim preserves the
original import path for the LangGraph backend and its tests.
"""

from __future__ import annotations

from ai_team.core.spend_guard import (
    DEFAULT_BUDGET_ENV,
    DEFAULT_BUDGET_USD,
    BudgetExceededError,
    current_spend,
    record_usage,
    reset_spend_guard,
)

__all__ = [
    "DEFAULT_BUDGET_ENV",
    "DEFAULT_BUDGET_USD",
    "BudgetExceededError",
    "current_spend",
    "record_usage",
    "reset_spend_guard",
]
