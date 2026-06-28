"""
LLM call observability hooks for CrewAI.

Registers before/after LLM call hooks that log:
- Role, model, iteration count before each call
- Empty/None responses after each call (the "None or empty" failure mode)
- Response length for quick size monitoring

Call register_llm_observability_hooks() once at flow startup (e.g. in kickoff()).
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

_REGISTERED = False


def register_llm_observability_hooks() -> None:
    """Register global CrewAI LLM hooks for observability. Idempotent."""
    global _REGISTERED
    if _REGISTERED:
        return

    try:
        from crewai.hooks import register_after_llm_call_hook, register_before_llm_call_hook
    except ImportError:
        logger.warning("llm_observability_skip", reason="crewai.hooks not available")
        return

    def _before_hook(context: object) -> None:
        role = getattr(getattr(context, "agent", None), "role", "unknown")
        model = getattr(getattr(context, "llm", None), "model", "unknown")
        iterations = getattr(context, "iterations", None)
        msg_count = len(getattr(context, "messages", []))
        logger.info(
            "llm_call_started",
            agent_role=role,
            model=model,
            iteration=iterations,
            message_count=msg_count,
        )

    def _after_hook(context: object) -> str | None:
        role = getattr(getattr(context, "agent", None), "role", "unknown")
        model = getattr(getattr(context, "llm", None), "model", "unknown")
        response = getattr(context, "response", None)

        if not response:
            logger.error(
                "llm_call_empty_response",
                agent_role=role,
                model=model,
                response_repr=repr(response),
            )
        else:
            logger.debug(
                "llm_call_completed",
                agent_role=role,
                model=model,
                response_len=len(response),
            )
        return None  # Don't modify response

    register_before_llm_call_hook(_before_hook)
    register_after_llm_call_hook(_after_hook)
    _REGISTERED = True
    logger.info("llm_observability_hooks_registered")


_SPEND_GUARD_REGISTERED = False


def register_crewai_spend_guard() -> None:
    """Register a LiteLLM success callback that feeds the shared spend guard.

    CrewAI routes every LLM call through LiteLLM, which reports the real
    per-call cost as ``response_cost`` in the success event. Recording it lets
    the per-run budget ceiling (``AI_TEAM_RUN_BUDGET_USD``) abort a runaway
    crash/retry loop on the CrewAI backend, matching the LangGraph backend.

    Idempotent. The actual budget reset happens per run via ``reset_spend_guard``.
    """
    global _SPEND_GUARD_REGISTERED
    if _SPEND_GUARD_REGISTERED:
        return
    try:
        import litellm
        from litellm.integrations.custom_logger import CustomLogger
    except ImportError:
        logger.warning("crewai_spend_guard_skip", reason="litellm not available")
        return

    from ai_team.core.spend_guard import record_usage

    class _SpendGuardLogger(CustomLogger):  # type: ignore[misc]
        def log_success_event(
            self,
            kwargs: dict,
            response_obj: object,
            start_time: object,
            end_time: object,
        ) -> None:
            cost = kwargs.get("response_cost")
            try:
                cost_f = float(cost) if cost is not None else 0.0
            except (TypeError, ValueError):
                cost_f = 0.0
            usage = getattr(response_obj, "usage", None)
            total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
            # record_usage raises BudgetExceededError when the ceiling is crossed;
            # let it propagate to abort the run.
            record_usage(cost_f, total_tokens)

    litellm.callbacks = [*getattr(litellm, "callbacks", []), _SpendGuardLogger()]
    _SPEND_GUARD_REGISTERED = True
    logger.info("crewai_spend_guard_registered")
