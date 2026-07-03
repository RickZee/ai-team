"""Per-run, backend-agnostic spend guard.

A repeatedly-crashing run (e.g. a model that keeps emitting malformed
tool-calls) can otherwise loop through many LLM calls — bounded only by the
phase/guardrail retry caps and the graph recursion limit — and quietly burn
money. This module tracks cumulative LLM spend for the current run and aborts
once a configurable ceiling is crossed.

Both OpenRouter backends feed it real per-call cost (no estimation):

- **LangGraph** records from the httpx response hook in ``langgraph_chat``,
  reading OpenRouter's ``usage.cost``.
- **CrewAI** records via a LiteLLM success callback (see
  ``register_crewai_spend_guard``), reading LiteLLM's ``response_cost``.

When the ceiling is exceeded :func:`record_usage` raises
:class:`BudgetExceededError`, which propagates out of the run and fails it with
a clear message instead of continuing to spend.

Isolation model (why this is not a process-global singleton):

Concurrent runs in one process (the web Compare tab) used to share one
module-level state — each run's ``reset_spend_guard`` wiped the others'
accumulation, and combined spend counted against whichever budget was set
last. State now lives in a :mod:`contextvars` ContextVar. Each run calls
:func:`reset_spend_guard` at its start *inside its own execution context*
(LangGraph: the producer thread; CrewAI: its own subprocess), so recording
and enforcement are per-run. A ``run_id``-keyed registry additionally lets
the web API read any run's spend cross-thread via
``current_spend(run_id=...)``.

Code that never calls ``reset_spend_guard`` (or records from a context that
didn't) falls back to a legacy process-global state, preserving single-run CLI
behavior.
"""

from __future__ import annotations

import contextvars
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_BUDGET_ENV = "AI_TEAM_RUN_BUDGET_USD"
# Conservative default: most demo runs cost cents. A run that blows past this is
# almost certainly looping. 0 (or unset → this default) can be overridden per run.
DEFAULT_BUDGET_USD = 5.0

# How many finished runs' spend snapshots to keep readable via run_id.
_REGISTRY_MAX = 50


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
    run_id: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)


# Legacy process-global fallback for contexts that never called reset.
_global_state = _SpendState()

# Active state for the current execution context (thread/task/process).
_ctx_state: contextvars.ContextVar[_SpendState | None] = contextvars.ContextVar(
    "spend_guard_state", default=None
)

# run_id -> state, for cross-thread reads (web API). Bounded.
_registry: OrderedDict[str, _SpendState] = OrderedDict()
_registry_lock = threading.Lock()


def _resolve_default_budget() -> float:
    raw = os.environ.get(DEFAULT_BUDGET_ENV)
    if raw is None or raw.strip() == "":
        return DEFAULT_BUDGET_USD
    try:
        return max(0.0, float(raw))
    except ValueError:
        logger.warning("spend_guard_bad_budget_env", value=raw, fallback=DEFAULT_BUDGET_USD)
        return DEFAULT_BUDGET_USD


def _active_state() -> _SpendState:
    return _ctx_state.get() or _global_state


def reset_spend_guard(budget_usd: float | None = None, run_id: str | None = None) -> None:
    """Start a fresh spend context for a new run.

    Args:
        budget_usd: Ceiling in USD. ``None`` resolves from the
            ``AI_TEAM_RUN_BUDGET_USD`` env var (or the built-in default).
            ``0`` disables the ceiling (tracking still runs).
        run_id: When provided, the run's spend is additionally readable
            cross-thread via ``current_spend(run_id=...)``.

    The new state binds to the *current execution context*: subsequent
    ``record_usage`` calls in this thread/task (and children that inherit the
    context, e.g. ``asyncio.to_thread``) hit this run's budget only. The
    legacy global state is also re-pointed for single-run CLI compatibility.
    """
    resolved = _resolve_default_budget() if budget_usd is None else max(0.0, budget_usd)
    state = _SpendState(budget_usd=resolved, run_id=run_id)
    _ctx_state.set(state)
    if run_id:
        with _registry_lock:
            _registry[run_id] = state
            while len(_registry) > _REGISTRY_MAX:
                _registry.popitem(last=False)
    # Single-run CLI paths read the global; keep it in sync with the most
    # recent reset so behavior there is unchanged.
    with _global_state._lock:
        _global_state.budget_usd = resolved
        _global_state.spent_usd = 0.0
        _global_state.total_tokens = 0
        _global_state.calls = 0
        _global_state.run_id = run_id
    logger.info("spend_guard_reset", budget_usd=resolved, run_id=run_id)


def record_usage(cost_usd: float, total_tokens: int = 0) -> None:
    """Add one LLM call's spend; raise if the ceiling is now exceeded.

    Args:
        cost_usd: Cost of this call in USD (from the OpenRouter response).
        total_tokens: Token count for this call (for diagnostics).

    Raises:
        BudgetExceededError: If a non-zero budget is set and cumulative spend
            now exceeds it.
    """
    state = _active_state()
    with state._lock:
        state.spent_usd += max(0.0, cost_usd)
        state.total_tokens += max(0, total_tokens)
        state.calls += 1
        budget = state.budget_usd
        spent = state.spent_usd
        calls = state.calls
    if budget > 0 and spent > budget:
        logger.error(
            "spend_guard_budget_exceeded",
            spent_usd=round(spent, 4),
            budget_usd=budget,
            calls=calls,
            run_id=state.run_id,
        )
        raise BudgetExceededError(
            f"Run spend ${spent:.4f} exceeded budget ${budget:.4f} after {calls} LLM calls. "
            f"Aborting to avoid runaway cost (likely a crash/retry loop). "
            f"Raise the ceiling with {DEFAULT_BUDGET_ENV} if this is expected."
        )


def current_spend(run_id: str | None = None) -> dict[str, float | int | str | None]:
    """Snapshot of a run's spend.

    Args:
        run_id: Read a specific run's spend cross-thread (web API). ``None``
            reads the current execution context's state (or the legacy global).
    """
    if run_id is not None:
        with _registry_lock:
            state = _registry.get(run_id)
        if state is None:
            return {
                "budget_usd": 0.0,
                "spent_usd": 0.0,
                "total_tokens": 0,
                "calls": 0,
                "run_id": run_id,
            }
    else:
        state = _active_state()
    with state._lock:
        return {
            "budget_usd": state.budget_usd,
            "spent_usd": round(state.spent_usd, 6),
            "total_tokens": state.total_tokens,
            "calls": state.calls,
            "run_id": state.run_id,
        }
