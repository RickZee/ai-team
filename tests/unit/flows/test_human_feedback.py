"""Unit tests for human feedback handler and parsing."""

from __future__ import annotations

import pytest

from ai_team.flows.human_feedback import (
    FeedbackType,
    HumanFeedbackRequest,
    HumanFeedbackResult,
    HumanFeedbackHandler,
    MockHumanFeedbackHandler,
    parse_feedback_response,
)


class TestParseFeedbackResponse:
    """Tests for parse_feedback_response."""

    def test_matches_option_case_insensitive(self) -> None:
        options = ["Proceed as-is", "Add clarification"]
        result = parse_feedback_response("proceed as-is", options, FeedbackType.APPROVAL)
        assert result.selected_option == "Proceed as-is"
        assert result.raw_response == "proceed as-is"

    def test_free_text_when_no_option_match(self) -> None:
        options = ["Yes", "No"]
        result = parse_feedback_response("I want to add more details", options, FeedbackType.CLARIFICATION)
        assert result.selected_option is None
        assert result.free_text == "I want to add more details"

    def test_approval_negative_option(self) -> None:
        options = ["Confirm", "Reject"]
        result = parse_feedback_response("Reject", options, FeedbackType.OVERRIDE)
        assert result.accepted is False

    def test_approval_positive_option(self) -> None:
        options = ["Allow", "Reject"]
        result = parse_feedback_response("Allow", options, FeedbackType.OVERRIDE)
        assert result.accepted is True


class TestHumanFeedbackRequest:
    """Tests for HumanFeedbackRequest model."""

    def test_minimal_request(self) -> None:
        req = HumanFeedbackRequest(question="Continue?")
        assert req.question == "Continue?"
        assert req.feedback_type == FeedbackType.CLARIFICATION
        assert req.context == {}
        assert req.options == []

    def test_full_request(self) -> None:
        req = HumanFeedbackRequest(
            question="Proceed?",
            feedback_type=FeedbackType.ESCALATION,
            context={"phase": "testing", "retries": 3},
            options=["Retry", "Abort"],
            default_option="Abort",
            project_id="proj-1",
        )
        assert req.default_option == "Abort"
        assert req.project_id == "proj-1"


class TestMockHumanFeedbackHandler:
    """Tests for MockHumanFeedbackHandler for automated testing."""

    def test_returns_preloaded_responses(self) -> None:
        handler = MockHumanFeedbackHandler(preloaded_responses=["Proceed", "Abort"])
        r1 = handler.request_feedback("Q?", {}, ["Proceed", "Abort"])
        assert r1 == "Proceed"
        r2 = handler.request_feedback("Q?", {}, ["Proceed", "Abort"])
        assert r2 == "Abort"

    def test_returns_default_when_preloaded_empty(self) -> None:
        handler = MockHumanFeedbackHandler(default_response="Default")
        r = handler.request_feedback("Q?", {}, [])
        assert r == "Default"

    def test_request_feedback_structured_uses_mock(self) -> None:
        handler = MockHumanFeedbackHandler(preloaded_responses=["Proceed as-is"])
        result = handler.request_feedback_structured(
            "Clarify?",
            {"phase": "planning"},
            ["Proceed as-is", "Add clarification"],
            feedback_type=FeedbackType.APPROVAL,
        )
        assert isinstance(result, HumanFeedbackResult)
        assert result.raw_response == "Proceed as-is"
        assert result.selected_option == "Proceed as-is"


class TestHumanFeedbackHandler:
    """Tests for HumanFeedbackHandler (with UI callback to avoid stdin)."""

    def test_ui_callback_used_when_set(self) -> None:
        def callback(question: str, context: dict, options: list) -> str:
            assert "Clarify" in question
            return "Proceed"

        handler = HumanFeedbackHandler(timeout_seconds=0, use_ui_callback=callback)
        r = handler.request_feedback("Clarify?", {"x": 1}, ["Proceed", "Abort"])
        assert r == "Proceed"

    def test_ui_callback_exception_returns_default(self) -> None:
        def callback(_q: str, _c: dict, _o: list) -> str:
            raise RuntimeError("UI error")

        handler = HumanFeedbackHandler(
            timeout_seconds=0,
            default_response="Fallback",
            use_ui_callback=callback,
        )
        r = handler.request_feedback("Q?", {}, [])
        assert r == "Fallback"
