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
