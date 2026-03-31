"""
Guardrail graph nodes (Phase 5): behavioral, security, quality with retry routing.

Each subgraph compiles agent work as node ``agents``, then runs guardrails sequentially.
Failed checks with remaining retries route through ``retry_wrap`` back to ``agents``.
"""

from __future__ import annotations

import re
from typing import Any, Literal

import structlog
from ai_team.backends.langgraph_backend.graphs.guardrail_hooks import (
    concat_recent_ai_content,
)
from ai_team.backends.langgraph_backend.graphs.state import LangGraphSubgraphState
from ai_team.guardrails.behavioral import (
    GuardrailResult as BehavioralGR,
)
from ai_team.guardrails.behavioral import (
    reasoning_guardrail,
    role_adherence_guardrail,
    scope_control_guardrail,
)
from ai_team.guardrails.quality import (
    GuardrailResult as QualityGR,
)
from ai_team.guardrails.quality import (
    code_quality_guardrail,
)
from ai_team.guardrails.security import (
    GuardrailResult as SecurityGR,
)
from ai_team.guardrails.security import (
    code_safety_guardrail,
    secret_detection_guardrail,
)
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

logger = structlog.get_logger(__name__)

MAX_SUBGRAPH_GUARDRAIL_RETRIES = 3
MIN_REASONING_FOR_CHECK = 80


def _worst_behavioral(results: list[BehavioralGR]) -> BehavioralGR:
    """Prefer first failure, then first warn, else last pass."""
    if not results:
        return BehavioralGR(
            status="pass",
            message="No behavioral checks applied.",
            retry_allowed=True,
        )
    for r in results:
        if r.status == "fail":
            return r
    for r in results:
        if r.status == "warn":
            return r
    return results[-1]


def _behavioral_stack(
    text: str,
    role: str,
    project_description: str | None,
    *,
    is_supervisor: bool = False,
) -> BehavioralGR:
    parts: list[BehavioralGR] = []
    if project_description and project_description.strip():
        parts.append(scope_control_guardrail(text, project_description))
    parts.append(role_adherence_guardrail(text, role, is_supervisor=is_supervisor))
    if len(text.strip()) >= MIN_REASONING_FOR_CHECK:
        parts.append(reasoning_guardrail(text))
    return _worst_behavioral(parts)


def _serialize_behavioral(gr: BehavioralGR) -> dict[str, Any]:
    return {
        "phase": "behavioral",
        "status": gr.status,
        "message": gr.message,
        "retry_allowed": gr.retry_allowed,
        "details": gr.details,
    }


def _serialize_security(gr: SecurityGR) -> dict[str, Any]:
    return {
        "phase": "security",
        "status": gr.status,
        "message": gr.message,
        "retry_allowed": gr.retry_allowed,
        "details": gr.details,
    }


def _merge_security_results(code: str) -> SecurityGR:
    """Run code safety then secret detection; worst outcome wins."""
    a = code_safety_guardrail(code)
    b = secret_detection_guardrail(code)
    for r in (a, b):
        if r.status == "fail":
            return r
    for r in (a, b):
        if r.status == "warn":
            return r
    return a


def _serialize_quality(gr: QualityGR) -> dict[str, Any]:
    status: Literal["pass", "fail", "warn"] = "pass" if gr.passed else "warn"
    return {
        "phase": "quality",
        "status": status,
        "message": gr.message,
        "retry_allowed": True,
        "details": {"score": gr.score, "suggestions": gr.suggestions},
    }


def make_behavioral_guardrail_node(
    behavioral_role: str,
    *,
    behavioral_only_message_names: frozenset[str] | None = None,
):
    """Factory: role used for role_adherence (per subgraph).

    For supervisor subgraphs, pass ``behavioral_only_message_names`` with the
    supervisor's graph name so worker outputs are not scanned as the supervisor role.
    """

    def behavioral_guardrail_node(state: LangGraphSubgraphState) -> dict[str, Any]:
        messages = state.get("messages") or []
        text = concat_recent_ai_content(
            list(messages), only_message_names=behavioral_only_message_names
        )
        if not text.strip():
            gr = BehavioralGR(
                status="pass",
                message="No assistant output to validate.",
                retry_allowed=True,
            )
            return {"guardrail_checks": [_serialize_behavioral(gr)]}
        desc = (state.get("project_description") or "").strip() or None
        gr = _behavioral_stack(
            text,
            behavioral_role,
            desc,
            is_supervisor=behavioral_only_message_names is not None,
        )
        return {"guardrail_checks": [_serialize_behavioral(gr)]}

    return behavioral_guardrail_node


def security_guardrail_node(state: LangGraphSubgraphState) -> dict[str, Any]:
    messages = state.get("messages") or []
    text = concat_recent_ai_content(list(messages))
    if not text.strip():
        gr = SecurityGR(
            status="pass",
            message="No assistant output to scan.",
            retry_allowed=True,
        )
        return {"guardrail_checks": [_serialize_security(gr)]}
    code_blocks = _extract_fenced_code(text)
    scan_text = code_blocks if code_blocks else text
    merged = _merge_security_results(scan_text)
    return {"guardrail_checks": [_serialize_security(merged)]}


def _looks_like_python_code(text: str) -> bool:
    """Avoid running ``ast.parse`` on conversational prose (e.g. stub LLM tests)."""
    s = text.strip()
    if not s:
        return False
    if "```" in s or "def " in s or "class " in s or "import " in s:
        return True
    if len(s) > 400 and ("return " in s or "self." in s):
        return True
    return False


_FENCED_CODE_RE = re.compile(
    r"```(?:python|py)\s*\n(.*?)```",
    re.DOTALL,
)


def _extract_fenced_code(text: str) -> str:
    """Return concatenated content of fenced code blocks, or empty string."""
    blocks = _FENCED_CODE_RE.findall(text)
    return "\n\n".join(b.strip() for b in blocks if b.strip())


def quality_guardrail_node(state: LangGraphSubgraphState) -> dict[str, Any]:
    messages = state.get("messages") or []
    text = concat_recent_ai_content(list(messages))
    if not text.strip():
        q = QualityGR(
            passed=True,
            score=100,
            message="No assistant output for quality scan.",
            suggestions=[],
        )
        return {"guardrail_checks": [_serialize_quality(q)]}

    code_to_check = _extract_fenced_code(text)
    if not code_to_check:
        q = QualityGR(
            passed=True,
            score=100,
            message="Skipped code-quality scan — no fenced code blocks in output.",
            suggestions=[],
        )
        return {"guardrail_checks": [_serialize_quality(q)]}

    gr = code_quality_guardrail(code_to_check, "python")
    return {"guardrail_checks": [_serialize_quality(gr)]}


def retry_wrap_node(state: LangGraphSubgraphState) -> dict[str, Any]:
    """Increment retry counter before re-entering agent subgraph."""
    n = int(state.get("guardrail_retry_count") or 0) + 1
    logger.info(
        "guardrail_retry_wrap", attempt=n, max_retries=MAX_SUBGRAPH_GUARDRAIL_RETRIES
    )
    return {"guardrail_retry_count": n}


def guardrail_terminal_node(state: LangGraphSubgraphState) -> dict[str, Any]:
    """Mark terminal guardrail failure after max retries."""
    return {"guardrail_terminal": True}


def _last_phase_check(
    state: LangGraphSubgraphState,
    phase: str,
) -> dict[str, Any] | None:
    checks = state.get("guardrail_checks") or []
    for c in reversed(checks):
        if c.get("phase") == phase:
            return c
    return None


def route_after_behavioral(
    state: LangGraphSubgraphState,
) -> Literal["security", "retry_wrap", "guardrail_terminal"]:
    last = _last_phase_check(state, "behavioral")
    if not last or last.get("status") != "fail":
        logger.debug("route_after_behavioral", decision="pass", status=last.get("status") if last else None)
        return "security"
    logger.info("route_after_behavioral", decision="fail", message=last.get("message"))
    if not last.get("retry_allowed", True):
        return "guardrail_terminal"
    if int(state.get("guardrail_retry_count") or 0) >= MAX_SUBGRAPH_GUARDRAIL_RETRIES:
        return "guardrail_terminal"
    return "retry_wrap"


def route_after_security(
    state: LangGraphSubgraphState,
) -> Literal["quality", "retry_wrap", "guardrail_terminal"]:
    last = _last_phase_check(state, "security")
    if not last or last.get("status") != "fail":
        logger.debug("route_after_security", decision="pass", status=last.get("status") if last else None)
        return "quality"
    logger.info("route_after_security", decision="fail", message=last.get("message"))
    if not last.get("retry_allowed", True):
        return "guardrail_terminal"
    if int(state.get("guardrail_retry_count") or 0) >= MAX_SUBGRAPH_GUARDRAIL_RETRIES:
        return "guardrail_terminal"
    return "retry_wrap"


def route_after_quality(
    state: LangGraphSubgraphState,
) -> Literal["retry_wrap", "guardrail_terminal", "__end__"]:
    last = _last_phase_check(state, "quality")
    if not last or last.get("status") != "fail":
        logger.debug("route_after_quality", decision="pass", status=last.get("status") if last else None)
        return "__end__"
    logger.info("route_after_quality", decision="fail", message=last.get("message"), details=last.get("details"))
    if not last.get("retry_allowed", True):
        return "guardrail_terminal"
    if int(state.get("guardrail_retry_count") or 0) >= MAX_SUBGRAPH_GUARDRAIL_RETRIES:
        return "guardrail_terminal"
    return "retry_wrap"


def wrap_agents_with_guardrails(
    agents_compiled: CompiledStateGraph,
    *,
    behavioral_role: str,
    behavioral_only_message_names: frozenset[str] | None = None,
) -> CompiledStateGraph:
    """
    Wrap a compiled agent subgraph (supervisor or ReAct) with guardrail nodes.

    Flow: agents → behavioral → security → quality → END, with retry_wrap → agents.
    """
    g = StateGraph(LangGraphSubgraphState)
    behavioral = make_behavioral_guardrail_node(
        behavioral_role,
        behavioral_only_message_names=behavioral_only_message_names,
    )

    g.add_node("agents", agents_compiled)
    g.add_node("behavioral", behavioral)
    g.add_node("security", security_guardrail_node)
    g.add_node("quality", quality_guardrail_node)
    g.add_node("retry_wrap", retry_wrap_node)
    g.add_node("guardrail_terminal", guardrail_terminal_node)

    g.add_edge(START, "agents")
    g.add_edge("agents", "behavioral")
    g.add_conditional_edges(
        "behavioral",
        route_after_behavioral,
        {
            "security": "security",
            "retry_wrap": "retry_wrap",
            "guardrail_terminal": "guardrail_terminal",
        },
    )
    g.add_conditional_edges(
        "security",
        route_after_security,
        {
            "quality": "quality",
            "retry_wrap": "retry_wrap",
            "guardrail_terminal": "guardrail_terminal",
        },
    )
    g.add_conditional_edges(
        "quality",
        route_after_quality,
        {
            "retry_wrap": "retry_wrap",
            "guardrail_terminal": "guardrail_terminal",
            "__end__": END,
        },
    )
    g.add_edge("retry_wrap", "agents")
    g.add_edge("guardrail_terminal", END)

    compiled = g.compile()
    logger.info(
        "guardrail_wrapped_subgraph",
        behavioral_role=behavioral_role,
    )
    return compiled
