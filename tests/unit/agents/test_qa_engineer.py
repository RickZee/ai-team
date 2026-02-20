"""Unit tests for QA Engineer agent, quality gates, and feedback for developers."""

import pytest
from unittest.mock import patch

from langchain_ollama import ChatOllama

from ai_team.agents.base import BaseAgent
from ai_team.agents.qa_engineer import (
    create_qa_engineer,
    quality_gate_passed,
    feedback_for_developers,
    MIN_COVERAGE_THRESHOLD_DEFAULT,
)
from ai_team.models.qa_models import (
    TestResult,
    TestExecutionResult,
    CoverageReport,
    BugReport,
)
from ai_team.tools.qa_tools import get_qa_tools


def _identity_llm(llm: object) -> object:
    """Pass-through so CrewAI uses our LLM as-is in tests."""
    return llm


@pytest.fixture
def mock_llm() -> ChatOllama:
    return ChatOllama(model="qwen3:14b", base_url="http://localhost:11434")


@pytest.fixture
def qa_config() -> dict:
    return {
        "qa_engineer": {
            "role": "QA Engineer / Test Automation Specialist",
            "goal": "Ensure code quality through comprehensive testing, find bugs before deployment.",
            "backstory": "QA lead who has prevented countless production incidents, believes in test pyramids.",
            "verbose": True,
            "allow_delegation": False,
            "max_iter": 12,
            "memory": True,
        },
    }


class TestCreateQaEngineer:
    def test_create_qa_engineer_returns_base_agent(
        self, mock_llm: ChatOllama, qa_config: dict
    ) -> None:
        with patch("ai_team.agents.base.get_settings") as mock_settings, patch(
            "ai_team.agents.base.LLM", return_value=mock_llm
        ), patch("crewai.agent.core.create_llm", side_effect=_identity_llm):
            mock_settings.return_value.ollama.get_model_for_role.return_value = "qwen3:14b"
            mock_settings.return_value.ollama.base_url = "http://localhost:11434"
            mock_settings.return_value.ollama.request_timeout = 300
            mock_settings.return_value.ollama.max_retries = 3
            mock_settings.return_value.guardrails.security_enabled = False
            agent = create_qa_engineer(agents_config=qa_config)
        assert isinstance(agent, BaseAgent)
        assert agent.role_name == "qa_engineer"
        assert agent.role == "QA Engineer / Test Automation Specialist"
        assert agent.allow_delegation is False
        assert agent.max_iter == 12
        expected_tools = get_qa_tools()
        assert len(agent.tools) == len(expected_tools)

    def test_min_coverage_threshold_default(self) -> None:
        assert MIN_COVERAGE_THRESHOLD_DEFAULT == 0.8


class TestQualityGatePassed:
    def test_passes_when_coverage_above_threshold_and_no_critical_bugs(self) -> None:
        result = TestResult(
            execution_results=TestExecutionResult(passed=10, failed=0, total=10),
            coverage_report=CoverageReport(line_coverage=0.85, branch_coverage=0.8),
            bug_reports=[],
        )
        assert quality_gate_passed(result) is True

    def test_fails_when_coverage_below_threshold(self) -> None:
        result = TestResult(
            execution_results=TestExecutionResult(passed=5, failed=0, total=5),
            coverage_report=CoverageReport(line_coverage=0.75, branch_coverage=0.7),
            bug_reports=[],
        )
        assert quality_gate_passed(result) is False

    def test_fails_when_critical_bug_present(self) -> None:
        result = TestResult(
            execution_results=TestExecutionResult(passed=10, failed=0, total=10),
            coverage_report=CoverageReport(line_coverage=0.9, branch_coverage=0.85),
            bug_reports=[
                BugReport(
                    title="Data loss",
                    severity="critical",
                    reproduction_steps="Save then reload",
                ),
            ],
        )
        assert quality_gate_passed(result) is False

    def test_custom_min_coverage(self) -> None:
        result = TestResult(
            execution_results=TestExecutionResult(passed=5, failed=0, total=5),
            coverage_report=CoverageReport(line_coverage=0.7, branch_coverage=0.65),
            bug_reports=[],
        )
        assert quality_gate_passed(result, min_coverage=0.6) is True
        assert quality_gate_passed(result, min_coverage=0.8) is False


class TestFeedbackForDevelopers:
    def test_includes_failed_tests_and_coverage_when_below_threshold(self) -> None:
        result = TestResult(
            execution_results=TestExecutionResult(
                passed=3,
                failed=2,
                errors=0,
                total=5,
                failed_tests=["test_foo", "test_bar"],
                output="AssertionError: expected 1 got 0",
            ),
            coverage_report=CoverageReport(line_coverage=0.7, branch_coverage=0.65),
            bug_reports=[],
        )
        feedback = feedback_for_developers(result)
        assert "2 failed" in feedback or "failed" in feedback
        assert "test_foo" in feedback or "Failed tests" in feedback
        assert "70%" in feedback or "0.7" in feedback or "below" in feedback

    def test_includes_critical_and_high_bugs(self) -> None:
        result = TestResult(
            execution_results=TestExecutionResult(passed=10, failed=0, total=10),
            coverage_report=CoverageReport(line_coverage=0.9, branch_coverage=0.85),
            bug_reports=[
                BugReport(
                    title="Crash on null",
                    severity="high",
                    reproduction_steps="Pass null to handler",
                    expected="No crash",
                    actual="Segfault",
                ),
            ],
        )
        feedback = feedback_for_developers(result)
        assert "Crash on null" in feedback or "high" in feedback
        assert "reproduction" in feedback.lower() or "Pass null" in feedback
