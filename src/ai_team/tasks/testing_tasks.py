"""
Testing tasks for the QA Engineer: test generation, execution, and code review.

Provides CrewAI Task definitions with guardrails. If tests fail, feedback is
returned to development tasks for fixes. Maximum 3 retry cycles before
escalating to human (see MAX_TEST_RETRY_CYCLES and ProjectState.max_test_retries).
"""

from __future__ import annotations

import json
import re
from typing import Any, List, Optional, Type

from crewai import Task

import structlog

from ai_team.guardrails.quality import coverage_guardrail
from ai_team.models.qa_models import CodeReviewReport
from ai_team.tools.test_tools import TestRunResult, validate_test_quality

logger = structlog.get_logger(__name__)

# Maximum retry cycles when tests fail before escalating to human (aligned with ProjectState.max_test_retries).
MAX_TEST_RETRY_CYCLES = 3

# Minimum coverage for test_execution guardrail (80% per prompt).
MIN_COVERAGE_THRESHOLD = 0.8


# -----------------------------------------------------------------------------
# Guardrail callables (task_output: str) -> bool for CrewAI Task
# -----------------------------------------------------------------------------


def _test_generation_guardrail(task_output: str) -> bool:
    """
    Guardrail: tests must have meaningful assertions and cover edge cases.
    Uses validate_test_quality on extracted test code; passes if assertions
    and edge-case hints are present.
    """
    if not task_output or not task_output.strip():
        return False
    # Use first substantial code block or full output as test code sample.
    code_match = re.search(r"```(?:\w+)?\s*\n(.*?)```", task_output, re.DOTALL)
    test_code = (code_match.group(1) if code_match else task_output).strip()
    if len(test_code) < 50:
        # No real code; check for at least assert and edge-case keywords in raw output.
        has_assert = "assert " in task_output or "assert_" in task_output or "assertEqual" in task_output
        has_edge = any(
            x in task_output.lower()
            for x in ["empty", "none", "zero", "null", "edge", "boundary", "invalid", "exception", "raise"]
        )
        return has_assert and has_edge
    report = validate_test_quality(test_code)
    return report.has_assertions and (report.edge_cases_mentioned or report.passed)


def _test_execution_guardrail(task_output: str) -> bool:
    """
    Guardrail: minimum 80% coverage, zero critical failures.
    Parses JSON or summary from task output and runs coverage_guardrail.
    """
    if not task_output or not task_output.strip():
        return False
    # Try to parse as TestRunResult-like JSON.
    try:
        # May be wrapped in markdown code block.
        raw = task_output.strip()
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if json_match:
            raw = json_match.group(1)
        data = json.loads(raw) if raw.strip().startswith("{") else None
    except json.JSONDecodeError:
        data = None

    if data:
        failed = int(data.get("failed", 0))
        errors = int(data.get("errors", 0))
        if failed > 0 or errors > 0:
            return False
        line_pct = data.get("line_coverage_pct")
        if line_pct is not None:
            cov_ratio = line_pct / 100.0 if line_pct > 1 else line_pct
            return cov_ratio >= MIN_COVERAGE_THRESHOLD
        # Build dict for coverage_guardrail.
        total_coverage = data.get("line_coverage_pct")
        if total_coverage is not None:
            total_coverage = total_coverage / 100.0 if total_coverage > 1 else total_coverage
        coverage_report = {"total_coverage": total_coverage or 0.0, "files": data.get("per_file_coverage", {})}
    else:
        # Heuristic: look for "X% coverage" and "passed" / "failed".
        coverage_report = {"total_coverage": 0.0}
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*coverage", task_output, re.IGNORECASE)
        if pct_match:
            coverage_report["total_coverage"] = float(pct_match.group(1)) / 100.0
        if re.search(r"\d+\s+failed|\d+\s+error", task_output, re.IGNORECASE):
            return False

    result = coverage_guardrail(coverage_report, min_coverage_threshold=MIN_COVERAGE_THRESHOLD)
    return result.passed


def _code_review_guardrail(task_output: str) -> bool:
    """
    Guardrail: no critical or high-severity findings.
    Parses CodeReviewReport-like output or scans for severity keywords.
    """
    if not task_output or not task_output.strip():
        return True  # No output treated as no findings.
    try:
        raw = task_output.strip()
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if json_match:
            raw = json_match.group(1)
        if raw.strip().startswith("{"):
            data = json.loads(raw)
            critical = int(data.get("critical_count", 0))
            high = int(data.get("high_count", 0))
            if critical > 0 or high > 0:
                return False
            findings = data.get("findings", [])
            for f in findings:
                sev = (f.get("severity") or "").lower()
                if sev in ("critical", "high"):
                    return False
            return True
    except json.JSONDecodeError:
        pass
    # Text fallback: fail if explicit critical/high finding mentioned.
    lower = task_output.lower()
    if re.search(r"severity\s*:\s*(critical|high)", lower) or re.search(
        r"(critical|high)\s*severity", lower
    ):
        return False
    return True


# -----------------------------------------------------------------------------
# Task factory functions
# -----------------------------------------------------------------------------


TEST_GENERATION_DESCRIPTION = (
    "Generate comprehensive tests for all code files. Cover unit and integration tests, "
    "meaningful assertions, and edge cases (empty, None, invalid input, exceptions)."
)

TEST_GENERATION_DESCRIPTION_WITH_INPUTS = (
    "Generate comprehensive tests for the following code files:\n\n{code_files_summary}\n\n"
    "Cover unit and integration tests, meaningful assertions, and edge cases "
    "(empty, None, invalid input, exceptions)."
)


def test_generation_task(
    qa_agent: Any,
    context: Optional[List[Task]] = None,
    guardrail_max_retries: int = 3,
    use_input_placeholder: bool = False,
) -> Task:
    """
    Create the test_generation task: generate comprehensive tests for all code files.

    Args:
        qa_agent: QA Engineer agent instance.
        context: Optional list of tasks whose outputs provide context (e.g. backend_implementation, frontend_implementation).
        guardrail_max_retries: Max retries when guardrail fails. Default 3.
        use_input_placeholder: If True, description includes {code_files_summary} for crew.kickoff(inputs=...).

    Returns:
        CrewAI Task for test generation.
    """
    description = (
        TEST_GENERATION_DESCRIPTION_WITH_INPUTS if use_input_placeholder else TEST_GENERATION_DESCRIPTION
    )
    return Task(
        description=description,
        agent=qa_agent,
        context=context or [],
        expected_output="List of CodeFile objects containing test files (path, content) for each test file generated.",
        guardrail=_test_generation_guardrail,
        guardrail_max_retries=guardrail_max_retries,
    )


def test_execution_task(
    qa_agent: Any,
    context: Optional[List[Task]] = None,
    guardrail_max_retries: int = 3,
    output_pydantic: Optional[Type[Any]] = None,
) -> Task:
    """
    Create the test_execution task: run all generated tests and report results.

    Args:
        qa_agent: QA Engineer agent instance.
        context: Optional list of tasks (e.g. test_generation) for context.
        guardrail_max_retries: Max retries when guardrail fails. Default 3.
        output_pydantic: Optional Pydantic model for structured output (e.g. TestRunResult).

    Returns:
        CrewAI Task for test execution.
    """
    return Task(
        description="Run all generated tests and report results. Use run_pytest (or equivalent) with coverage. Report pass/fail counts, duration, and line and branch coverage.",
        agent=qa_agent,
        context=context or [],
        expected_output="TestRunResult with pass/fail counts, coverage percentage, and raw output. Ensure zero critical failures and minimum 80% line coverage.",
        guardrail=_test_execution_guardrail,
        guardrail_max_retries=guardrail_max_retries,
        output_pydantic=output_pydantic or TestRunResult,
    )


def code_review_task(
    qa_agent: Any,
    context: Optional[List[Task]] = None,
    guardrail_max_retries: int = 3,
    output_pydantic: Optional[Type[Any]] = None,
) -> Task:
    """
    Create the code_review task: review all generated code for quality, security, best practices.

    Args:
        qa_agent: QA Engineer agent instance.
        context: Optional list of tasks (e.g. backend_implementation, frontend_implementation, test_execution).
        guardrail_max_retries: Max retries when guardrail fails. Default 3.
        output_pydantic: Optional Pydantic model for structured output (e.g. CodeReviewReport).

    Returns:
        CrewAI Task for code review.
    """
    return Task(
        description="Review all generated code for quality, security, and best practices. Produce a structured report with findings and severity (critical, high, medium, low). No critical or high-severity findings are allowed.",
        agent=qa_agent,
        context=context or [],
        expected_output="CodeReviewReport with findings and severity. Summary, critical_count, high_count, and passed=True only when there are no critical or high-severity findings.",
        guardrail=_code_review_guardrail,
        guardrail_max_retries=guardrail_max_retries,
        output_pydantic=output_pydantic or CodeReviewReport,
    )


def get_testing_tasks(
    qa_agent: Any,
    backend_implementation_task: Optional[Task] = None,
    frontend_implementation_task: Optional[Task] = None,
) -> List[Task]:
    """
    Build the full testing task chain: test_generation → test_execution → code_review.

    Context is wired so that:
    - test_generation depends on backend_implementation and frontend_implementation.
    - test_execution depends on test_generation.
    - code_review depends on backend_implementation, frontend_implementation, and test_execution.

    Retry logic: if tests fail, feedback should be returned to development tasks for fixes.
    Maximum MAX_TEST_RETRY_CYCLES (3) retry cycles before escalating to human.

    Args:
        qa_agent: QA Engineer agent.
        backend_implementation_task: Optional Task that produced backend code.
        frontend_implementation_task: Optional Task that produced frontend code.

    Returns:
        List of [test_generation_task, test_execution_task, code_review_task].
    """
    dev_context = []
    if backend_implementation_task is not None:
        dev_context.append(backend_implementation_task)
    if frontend_implementation_task is not None:
        dev_context.append(frontend_implementation_task)

    t_gen = test_generation_task(qa_agent, context=dev_context if dev_context else None)
    t_exec = test_execution_task(qa_agent, context=[t_gen])
    review_context: List[Task] = list(dev_context) + [t_exec]
    t_review = code_review_task(qa_agent, context=review_context if review_context else [t_exec])

    logger.info(
        "testing_tasks_created",
        has_backend_context=backend_implementation_task is not None,
        has_frontend_context=frontend_implementation_task is not None,
    )
    return [t_gen, t_exec, t_review]
