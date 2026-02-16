"""
Human-in-the-loop feedback handler for the AI Team flow.

Provides HumanFeedbackHandler for CLI and UI (Gradio) modes, structured
feedback types (Clarification, Approval, Escalation, Override), configurable
timeout with default action, and audit logging. Includes MockHumanFeedbackHandler
for automated testing.
"""

from __future__ import annotations

import threading
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -----------------------------------------------------------------------------
# Feedback types and structured models
# -----------------------------------------------------------------------------


class FeedbackType(str, Enum):
    """Type of human feedback request."""

    CLARIFICATION = "clarification"
    APPROVAL = "approval"
    ESCALATION = "escalation"
    OVERRIDE = "override"


class HumanFeedbackRequest(BaseModel):
    """Structured request for human feedback."""

    question: str = Field(..., description="Question or prompt shown to the user")
    feedback_type: FeedbackType = Field(
        default=FeedbackType.CLARIFICATION,
        description="Category of feedback",
    )
    context: Dict[str, Any] = Field(default_factory=dict, description="Relevant context (what failed, agent output)")
    options: List[str] = Field(default_factory=list, description="Structured options (e.g. Confirm, Simplify, Reject)")
    default_option: Optional[str] = Field(default=None, description="Option to use on timeout")
    project_id: Optional[str] = Field(default=None, description="Project ID for audit")


class HumanFeedbackResult(BaseModel):
    """Parsed human response for injection into agent context."""

    raw_response: str = Field(..., description="Original user input")
    selected_option: Optional[str] = Field(default=None, description="Matched option if any")
    free_text: str = Field(default="", description="Free-text part of the response")
    feedback_type: FeedbackType = Field(default=FeedbackType.CLARIFICATION)
    accepted: bool = Field(default=True, description="Whether user accepted/confirmed (for Approval/Override)")


def parse_feedback_response(
    response: str,
    options: List[str],
    feedback_type: FeedbackType = FeedbackType.CLARIFICATION,
) -> HumanFeedbackResult:
    """
    Parse human response into structured format.

    If response matches an option (case-insensitive, stripped), sets selected_option.
    Otherwise treats entire response as free_text. For Approval/Override, infers
    accepted from positive/negative wording or option match.
    """
    response = (response or "").strip()
    selected: Optional[str] = None
    for opt in options:
        if opt.strip().lower() == response.lower():
            selected = opt.strip()
            break
    free_text = response if not selected else ""
    accepted = True
    if feedback_type in (FeedbackType.APPROVAL, FeedbackType.OVERRIDE) and options:
        positive = ["yes", "confirm", "allow", "approve", "accept", "ok"]
        negative = ["no", "reject", "deny", "simplify", "disallow"]
        lower = response.lower()
        if any(n in lower for n in negative) and not any(p in lower for p in positive):
            accepted = False
        elif selected and selected.lower() in [n.lower() for n in negative]:
            accepted = False
    return HumanFeedbackResult(
        raw_response=response,
        selected_option=selected,
        free_text=free_text if not selected else "",
        feedback_type=feedback_type,
        accepted=accepted,
    )


# -----------------------------------------------------------------------------
# HumanFeedbackHandler
# -----------------------------------------------------------------------------

GradioCallback = Callable[[str, Dict[str, Any], List[str]], str]


class HumanFeedbackHandler:
    """
    Request feedback from the user via CLI (input()) or UI (Gradio callback).

    Supports configurable timeout with default action, structured options plus
    free-text, and audit logging for all human interactions.
    """

    def __init__(
        self,
        timeout_seconds: int = 300,
        default_response: str = "",
        use_ui_callback: Optional[GradioCallback] = None,
    ) -> None:
        self.timeout_seconds = max(0, timeout_seconds)
        self.default_response = default_response or ""
        self._ui_callback: Optional[GradioCallback] = None
        if use_ui_callback is not None:
            self._ui_callback = use_ui_callback
        self._response_holder: List[str] = []
        self._response_ready = threading.Event()

    def set_gradio_callback(self, callback: GradioCallback) -> None:
        """Register a Gradio callback for web UI mode."""
        self._ui_callback = callback

    def request_feedback(
        self,
        question: str,
        context: Dict[str, Any],
        options: List[str],
        *,
        default_option: Optional[str] = None,
        feedback_type: FeedbackType = FeedbackType.CLARIFICATION,
        project_id: Optional[str] = None,
    ) -> str:
        """
        Present question to user via Gradio UI or CLI prompt; return response.

        Includes context (what failed, what agents produced), structured options
        plus free-text. If timeout_seconds > 0 and no response in time, returns
        default_option or default_response. Logs all interactions for audit.
        """
        default = default_option if default_option is not None else self.default_response
        req = HumanFeedbackRequest(
            question=question,
            feedback_type=feedback_type,
            context=context,
            options=options,
            default_option=default,
            project_id=project_id,
        )
        logger.info(
            "human_feedback_request",
            project_id=project_id,
            feedback_type=feedback_type.value,
            options_count=len(options),
            has_default=bool(default),
        )

        if self._ui_callback is not None:
            try:
                out = self._ui_callback(question, context, options)
                response = (out or "").strip() or default
            except Exception as e:
                logger.warning("human_feedback_ui_callback_error", error=str(e))
                response = default
        else:
            response = self._request_feedback_cli(question, context, options, default)

        logger.info(
            "human_feedback_received",
            project_id=project_id,
            feedback_type=feedback_type.value,
            response_length=len(response),
            used_default=response == default and bool(default),
        )
        return response

    def _request_feedback_cli(
        self,
        question: str,
        context: Dict[str, Any],
        options: List[str],
        default: str,
    ) -> str:
        """Use input() for non-UI usage; optional timeout with default."""
        lines = [question, ""]
        if context:
            lines.append("Context:")
            for k, v in context.items():
                lines.append(f"  {k}: {v}")
            lines.append("")
        if options:
            lines.append("Options: " + " | ".join(options))
            lines.append("(Or type free text and press Enter)")
        if self.timeout_seconds > 0 and default:
            lines.append(f"(Timeout in {self.timeout_seconds}s → default: {default})")
        lines.append("")
        prompt = "\n".join(lines)

        if self.timeout_seconds <= 0:
            return (input(prompt) or default).strip()

        result: List[str] = [default]

        def read_input() -> None:
            try:
                value = input(prompt)
                result[0] = (value or default).strip()
            except EOFError:
                result[0] = default

        thread = threading.Thread(target=read_input, daemon=True)
        thread.start()
        thread.join(timeout=float(self.timeout_seconds))
        if thread.is_alive():
            logger.info(
                "human_feedback_timeout",
                timeout_seconds=self.timeout_seconds,
                default_used=default,
            )
        return result[0]

    def request_feedback_structured(
        self,
        question: str,
        context: Dict[str, Any],
        options: List[str],
        *,
        default_option: Optional[str] = None,
        feedback_type: FeedbackType = FeedbackType.CLARIFICATION,
        project_id: Optional[str] = None,
    ) -> HumanFeedbackResult:
        """
        Request feedback and parse into HumanFeedbackResult for injection
        into agent context.
        """
        raw = self.request_feedback(
            question=question,
            context=context,
            options=options,
            default_option=default_option,
            feedback_type=feedback_type,
            project_id=project_id,
        )
        return parse_feedback_response(raw, options, feedback_type)


# -----------------------------------------------------------------------------
# Mock handler for automated testing
# -----------------------------------------------------------------------------


class MockHumanFeedbackHandler(HumanFeedbackHandler):
    """
    Handler that returns predefined responses without prompting.

    Use for automated tests. Set preloaded_responses to a list of strings;
    each call to request_feedback pops the next one, or uses default_response.
    """

    def __init__(
        self,
        timeout_seconds: int = 0,
        default_response: str = "",
        preloaded_responses: Optional[List[str]] = None,
    ) -> None:
        super().__init__(timeout_seconds=timeout_seconds, default_response=default_response)
        self.preloaded_responses: List[str] = list(preloaded_responses or [])

    def request_feedback(
        self,
        question: str,
        context: Dict[str, Any],
        options: List[str],
        *,
        default_option: Optional[str] = None,
        feedback_type: FeedbackType = FeedbackType.CLARIFICATION,
        project_id: Optional[str] = None,
    ) -> str:
        """Return next preloaded response or default; no actual I/O."""
        logger.info(
            "mock_human_feedback",
            project_id=project_id,
            feedback_type=feedback_type.value,
            preloaded_remaining=len(self.preloaded_responses),
        )
        if self.preloaded_responses:
            return self.preloaded_responses.pop(0).strip()
        return (default_option or self.default_response or "").strip()
