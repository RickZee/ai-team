"""Lightweight guardrail passes on agent message history for LangGraph subgraphs."""

from __future__ import annotations

from typing import Any

import structlog
from ai_team.guardrails.security import GuardrailResult, code_safety_guardrail
from langchain_core.messages import AIMessage, BaseMessage

logger = structlog.get_logger(__name__)


def _concat_recent_ai_content(
    messages: list[BaseMessage],
    max_messages: int = 12,
    *,
    only_message_names: frozenset[str] | None = None,
) -> str:
    """Concatenate recent assistant text for scanning.

    When ``only_message_names`` is set (e.g. supervisor node name), only ``AIMessage``
    rows whose ``name`` is in that set are included. This avoids applying the
    manager role guardrail to delegated workers' legitimate code (PO, architect).
    """
    parts: list[str] = []
    for m in messages[-max_messages:]:
        if isinstance(m, AIMessage):
            if only_message_names is not None:
                n = (getattr(m, "name", None) or "").strip()
                if n not in only_message_names:
                    continue
            c = m.content
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, list):
                for block in c:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
    return "\n".join(parts)


concat_recent_ai_content = _concat_recent_ai_content


def planning_guardrail_result(state: dict[str, Any]) -> GuardrailResult:
    """Run code-safety scan on recent planning subgraph messages."""
    messages = state.get("messages") or []
    text = _concat_recent_ai_content(list(messages))
    if not text.strip():
        return GuardrailResult(status="pass", message="No assistant content to scan.")
    return code_safety_guardrail(text)


def development_guardrail_result(state: dict[str, Any]) -> GuardrailResult:
    """Security + quality proxy for development outputs (code-safety on text)."""
    return planning_guardrail_result(state)


def testing_guardrail_result(state: dict[str, Any]) -> GuardrailResult:
    """Validate testing subgraph assistant output."""
    return planning_guardrail_result(state)


def deployment_guardrail_result(state: dict[str, Any]) -> GuardrailResult:
    """Validate deployment subgraph assistant output (IaC / config text)."""
    return planning_guardrail_result(state)


def guardrail_post_hook(state: dict[str, Any]) -> dict[str, Any]:
    """
    ``post_model_hook``-compatible update: attach ``guardrail_result`` dict to state.

    Supervisor/agent state must include optional ``guardrail_result`` in schema if
    the compiled graph validates state keys; otherwise merge may drop unknown keys.
    """
    gr = planning_guardrail_result(state)
    return {
        "guardrail_result": {
            "status": gr.status,
            "message": gr.message,
            "retry_allowed": gr.retry_allowed,
        }
    }
