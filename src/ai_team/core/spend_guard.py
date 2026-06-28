"""Process-wide, backend-agnostic spend guard.

A repeatedly-crashing run (e.g. a model that keeps emitting malformed
tool-calls) can otherwise loop through many LLM calls — bounded only by the
phase/guardrail retry caps and the graph recursion limit — and quietly burn
money. This module tracks cumulative LLM spend for the current run and aborts
once a configurable ceiling is crossed.

Both backends feed it real per-call cost (no estimation):

- **LangGraph** records from the httpx response hook in ``langgraph_chat``,
  reading OpenRouter's ``usage.cost``.
- **CrewAI** records via a LiteLLM success callback (see
  ``register_crewai_spend_guard``), reading LiteLLM's ``response_cost``.

When the ceiling is exceeded :func:`record_usage` raises
:class:`BudgetExceededError`, which propagates out of the run and fails it with
a clear message instead of continuing to spend.

Budget is per-run: call :func:`reset_spend_guard` at the start of each run.
The default ceiling comes from ``AI_TEAM_RUN_BUDGET_USD`` (0 disables).
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_BUDGET_ENV = "AI_TEAM_RUN_BUDGET_USD"
# Conservative default: most demo runs cost cents. A run that blows past this is
# almost certainly looping. 0 (or unset → this default) can be overridden per run.
DEFAULT_BUDGET_USD = 5.0


class BudgetExceededError(BaseException):
    """Raised when cumulative run spend crosses the configured ceiling.

    Subclasses ``BaseException`` (not ``Exception``) on purpose: the phase
    subgraph nodes wrap ``sub.invoke`` in ``except Exception`` and convert
    failures into retryable error dicts. A budget abort must NOT be retryable —
    retrying is exactly what we're trying to stop — so it bypasses those handlers
    and propagates straight out of the graph invoke, like ``KeyboardInterrupt``.
    """


@dataclass
class _SpendState:
    budget_usd: float = 0.0
    spent_usd: float = 0.0
    total_tokens: int = 0
    calls: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)


_state = _SpendState()


def _resolve_default_budget() -> float:
    raw = os.environ.get(DEFAULT_BUDGET_ENV)
    if raw is None or raw.strip() == "":
        return DEFAULT_BUDGET_USD
    try:
        return max(0.0, float(raw))
    except ValueError:
        logger.warning("spend_guard_bad_budget_env", value=raw, fallback=DEFAULT_BUDGET_USD)
        return DEFAULT_BUDGET_USD


def reset_spend_guard(budget_usd: float | None = None) -> None:
    """Reset spend counters for a new run.

    Args:
        budget_usd: Ceiling in USD. ``None`` resolves from the
            ``AI_TEAM_RUN_BUDGET_USD`` env var (or the built-in default).
            ``0`` disables the ceiling (tracking still runs).
    """
    resolved = _resolve_default_budget() if budget_usd is None else max(0.0, budget_usd)
    with _state._lock:
        _state.budget_usd = resolved
        _state.spent_usd = 0.0
        _state.total_tokens = 0
        _state.calls = 0
    logger.info("spend_guard_reset", budget_usd=resolved)


def record_usage(cost_usd: float, total_tokens: int = 0) -> None:
    """Add one LLM call's spend; raise if the ceiling is now exceeded.

    Args:
        cost_usd: Cost of this call in USD (from the OpenRouter response).
        total_tokens: Token count for this call (for diagnostics).

    Raises:
        BudgetExceededError: If a non-zero budget is set and cumulative spend
            now exceeds it.
    """
    with _state._lock:
        _state.spent_usd += max(0.0, cost_usd)
        _state.total_tokens += max(0, total_tokens)
        _state.calls += 1
        budget = _state.budget_usd
        spent = _state.spent_usd
        calls = _state.calls
    if budget > 0 and spent > budget:
        logger.error(
            "spend_guard_budget_exceeded",
            spent_usd=round(spent, 4),
            budget_usd=budget,
            calls=calls,
        )
        raise BudgetExceededError(
            f"Run spend ${spent:.4f} exceeded budget ${budget:.4f} after {calls} LLM calls. "
            f"Aborting to avoid runaway cost (likely a crash/retry loop). "
            f"Raise the ceiling with {DEFAULT_BUDGET_ENV} if this is expected."
        )


def current_spend() -> dict[str, float | int]:
    """Snapshot of the current run's spend (for reporting/tests)."""
    with _state._lock:
        return {
            "budget_usd": _state.budget_usd,
            "spent_usd": round(_state.spent_usd, 6),
            "total_tokens": _state.total_tokens,
            "calls": _state.calls,
        }
