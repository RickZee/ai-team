"""
QA Engineer agent: test automation, coverage analysis, bug reporting, and quality gates.

Extends BaseAgent with tools for test generation, test execution, coverage,
bug reporting, and linting. Outputs TestResult (Pydantic) for quality gates.
Guardrail: generated code must have >80% test coverage. When tests fail,
provides feedback for developer agents to fix issues.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from ai_team.agents.base import BaseAgent, create_agent
from ai_team.models.qa_models import TestResult
from ai_team.tools.qa_tools import get_qa_tools

logger = structlog.get_logger(__name__)

# Guardrail: all generated code must have >80% test coverage
MIN_COVERAGE_THRESHOLD_DEFAULT = 0.8


def create_qa_engineer(
    *,
    tools: Optional[List[Any]] = None,
    before_task: Optional[Any] = None,
    after_task: Optional[Any] = None,
    guardrail_tools: bool = True,
    config_path: Optional[Path] = None,
    agents_config: Optional[Dict[str, Any]] = None,
) -> BaseAgent:
    """
    Create the QA Engineer agent with test_generator, test_runner, coverage_analyzer,
    bug_reporter, and lint_runner. Uses config from agents.yaml (qa_engineer section).
    """
    agent = create_agent(
        "qa_engineer",
        tools=tools if tools is not None else get_qa_tools(),
        before_task=before_task,
        after_task=after_task,
        guardrail_tools=guardrail_tools,
        config_path=config_path,
        agents_config=agents_config,
    )
    logger.info("qa_engineer_created", tools_count=len(agent.tools or []))
    return agent


def quality_gate_passed(
    result: TestResult,
    min_coverage: float = MIN_COVERAGE_THRESHOLD_DEFAULT,
    require_zero_critical_bugs: bool = True,
) -> bool:
    """
    Check quality gates: coverage >= min_coverage and (if required) no critical bugs.

    Args:
        result: TestResult from QA run.
        min_coverage: Minimum line coverage ratio (0-1). Default 0.8 (80%).
        require_zero_critical_bugs: If True, fail gate when any bug is critical.

    Returns:
        True if gates passed.
    """
    if result.coverage_report.line_coverage < min_coverage:
        return False
    if require_zero_critical_bugs:
        critical = [b for b in result.bug_reports if b.severity.lower() == "critical"]
        if critical:
            return False
    return True


def feedback_for_developers(result: TestResult) -> str:
    """
    Build actionable feedback for developer agents when tests fail or quality
    gates fail. Use in retry logic: if tests fail, pass this to developer
    agents for fixes.

    Args:
        result: TestResult from QA run.

    Returns:
        Human-readable feedback string.
    """
    parts: List[str] = []
    ex = result.execution_results
    if ex.failed > 0 or ex.errors > 0:
        parts.append(f"Tests: {ex.failed} failed, {ex.errors} errors, {ex.passed} passed.")
        if ex.failed_tests:
            parts.append("Failed tests: " + ", ".join(ex.failed_tests[:10]))
        if ex.output:
            parts.append("Last 500 chars of output:\n" + ex.output[-500:])
    cov = result.coverage_report
    if cov.line_coverage < MIN_COVERAGE_THRESHOLD_DEFAULT:
        parts.append(
            f"Coverage {cov.line_coverage:.1%} is below required {MIN_COVERAGE_THRESHOLD_DEFAULT:.0%}. "
            "Add or fix tests to meet the threshold."
        )
    for b in result.bug_reports:
        if b.severity.lower() in ("critical", "high"):
            parts.append(
                f"[{b.severity}] {b.title}: {b.reproduction_steps}. "
                f"Expected: {b.expected or 'N/A'}. Actual: {b.actual or 'N/A'}."
            )
    if result.feedback_for_developers:
        parts.append(result.feedback_for_developers)
    return "\n".join(parts) if parts else "No specific feedback."


__all__ = [
    "create_qa_engineer",
    "quality_gate_passed",
    "feedback_for_developers",
    "MIN_COVERAGE_THRESHOLD_DEFAULT",
]
