"""
Testing Crew: sequential test generation → execution → code review.

Single agent (QA Engineer), three tasks. Input: List[CodeFile] from Development Crew.
Output: TestRunResult + CodeReviewReport. Supports retry integration via get_feedback().
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Type

from crewai import Crew, Process
from crewai import Task
from pydantic import BaseModel, Field

import structlog

from ai_team.agents.qa_engineer import create_qa_engineer
from ai_team.config.settings import get_settings
from ai_team.memory import get_crew_embedder_config
from ai_team.models.development import CodeFile
from ai_team.models.qa_models import CodeReviewReport
from ai_team.tasks.testing_tasks import (
    code_review_task,
    test_execution_task,
    test_generation_task,
)
from ai_team.tools.test_tools import TestRunResult

logger = structlog.get_logger(__name__)


# -----------------------------------------------------------------------------
# Output model (TestRunResult + CodeReviewReport)
# -----------------------------------------------------------------------------


class TestingCrewOutput(BaseModel):
    """Result of the Testing Crew: test run and code review."""

    test_run_result: Optional[TestRunResult] = Field(
        default=None,
        description="Structured test execution result (pass/fail, coverage).",
    )
    code_review_report: Optional[CodeReviewReport] = Field(
        default=None,
        description="Structured code review with findings and severity.",
    )
    quality_gate_passed: bool = Field(
        default=False,
        description="True if tests pass, coverage meets threshold, and no critical/high findings.",
    )
    raw_outputs: List[str] = Field(
        default_factory=list,
        description="Raw task outputs in order [test_gen, test_exec, code_review] for debugging.",
    )


# -----------------------------------------------------------------------------
# Crew build and kickoff
# -----------------------------------------------------------------------------


def _code_files_to_summary(code_files: List[CodeFile], max_chars: int = 12000) -> str:
    """Serialize code files for crew input (path + content snippet)."""
    parts: List[str] = []
    total = 0
    for cf in code_files:
        block = f"--- {cf.path} ({cf.language}) ---\n{cf.content}\n"
        if total + len(block) > max_chars:
            parts.append(block[: max_chars - total] + "\n... (truncated)")
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts) if parts else "(no code files provided)"


def _parse_task_output_as_model(raw: Any, model: Type[BaseModel]) -> Optional[BaseModel]:
    """Parse task raw output (str or object with .raw) into a Pydantic model."""
    text: Optional[str] = None
    if isinstance(raw, str):
        text = raw
    elif hasattr(raw, "raw"):
        text = getattr(raw, "raw") or ""
    if not text or not text.strip():
        return None
    text = text.strip()
    # Try JSON inside markdown block first
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        text = json_match.group(1)
    if not text.strip().startswith("{"):
        return None
    try:
        data = json.loads(text)
        return model.model_validate(data)
    except (json.JSONDecodeError, Exception):
        return None


def _quality_gate_passed(
    test_run_result: Optional[TestRunResult],
    code_review_report: Optional[CodeReviewReport],
    min_line_coverage: float,
    min_branch_coverage: Optional[float],
) -> bool:
    """Check configurable quality gates: pass/fail and coverage thresholds."""
    if test_run_result is None:
        return False
    if not test_run_result.success or (test_run_result.failed or test_run_result.errors):
        return False
    line_pct = test_run_result.line_coverage_pct
    if line_pct is not None:
        ratio = line_pct / 100.0 if line_pct > 1 else line_pct
        if ratio < min_line_coverage:
            return False
    if min_branch_coverage is not None and test_run_result.branch_coverage_pct is not None:
        branch_ratio = (
            test_run_result.branch_coverage_pct / 100.0
            if test_run_result.branch_coverage_pct > 1
            else test_run_result.branch_coverage_pct
        )
        if branch_ratio < min_branch_coverage:
            return False
    if code_review_report is not None and not code_review_report.passed:
        return False
    return True


def create_testing_crew(
    qa_agent: Optional[Any] = None,
    guardrail_max_retries: Optional[int] = None,
    memory: bool = False,
    verbose: bool = False,
) -> Crew:
    """
    Build the Testing Crew: sequential process, QA Engineer only.

    Tasks: test_generation (with code_files_summary input) → test_execution → code_review.
    Guardrails: test quality validation, coverage enforcement (from settings when available).
    """
    agent = qa_agent if qa_agent is not None else create_qa_engineer()
    retries = guardrail_max_retries
    if retries is None:
        try:
            settings = get_settings()
            retries = settings.guardrails.quality_max_retries
        except Exception:
            retries = 3

    t_gen = test_generation_task(
        agent,
        context=[],
        guardrail_max_retries=retries,
        use_input_placeholder=True,
    )
    t_exec = test_execution_task(agent, context=[t_gen], guardrail_max_retries=retries)
    t_review = code_review_task(
        agent,
        context=[t_gen, t_exec],
        guardrail_max_retries=retries,
    )

    crew = Crew(
        agents=[agent],
        tasks=[t_gen, t_exec, t_review],
        process=Process.sequential,
        memory=memory,
        embedder=get_crew_embedder_config() if memory else None,
        verbose=verbose,
    )
    logger.info(
        "testing_crew_created",
        process="sequential",
        tasks=["test_generation", "test_execution", "code_review"],
    )
    return crew


def kickoff(
    code_files: List[CodeFile],
    qa_agent: Optional[Any] = None,
    guardrail_max_retries: Optional[int] = None,
    memory: bool = False,
    verbose: bool = False,
) -> TestingCrewOutput:
    """
    Run the Testing Crew on the given code files from the Development Crew.

    Args:
        code_files: List of CodeFile from Development Crew.
        qa_agent: Optional QA Engineer agent; created if not provided.
        guardrail_max_retries: Max retries per guardrail; uses settings if not set.
        memory: Enable crew memory.
        verbose: Verbose crew execution.

    Returns:
        TestingCrewOutput with test_run_result, code_review_report, and quality_gate_passed.
    """
    crew = create_testing_crew(
        qa_agent=qa_agent,
        guardrail_max_retries=guardrail_max_retries,
        memory=memory,
        verbose=verbose,
    )
    code_files_summary = _code_files_to_summary(code_files)
    inputs = {"code_files_summary": code_files_summary}

    crew_result = crew.kickoff(inputs=inputs)

    raw_outputs: List[str] = []
    if getattr(crew_result, "tasks_output", None):
        for out in crew_result.tasks_output:
            raw = out.raw if hasattr(out, "raw") else str(out)
            raw_outputs.append(raw)
    elif hasattr(crew_result, "raw"):
        raw_outputs.append(getattr(crew_result, "raw") or "")

    test_run_result: Optional[TestRunResult] = None
    code_review_report: Optional[CodeReviewReport] = None
    if len(raw_outputs) >= 2:
        test_run_result = _parse_task_output_as_model(raw_outputs[1], TestRunResult)
    if len(raw_outputs) >= 3:
        code_review_report = _parse_task_output_as_model(raw_outputs[2], CodeReviewReport)

    min_line = 0.8
    min_branch: Optional[float] = None
    try:
        settings = get_settings()
        min_line = settings.guardrails.test_coverage_min
    except Exception:
        pass

    quality_gate_passed = _quality_gate_passed(
        test_run_result,
        code_review_report,
        min_line_coverage=min_line,
        min_branch_coverage=min_branch,
    )

    return TestingCrewOutput(
        test_run_result=test_run_result,
        code_review_report=code_review_report,
        quality_gate_passed=quality_gate_passed,
        raw_outputs=raw_outputs,
    )


def get_feedback(
    output: TestingCrewOutput,
    *,
    include_review_findings: bool = True,
    max_raw_chars: int = 2000,
) -> Dict[str, Any]:
    """
    Format test failures and review findings as actionable feedback for the Development Crew.

    Use when test_execution or code_review fails so the Development Crew can fix and retry.

    Args:
        output: Result from Testing Crew kickoff().
        include_review_findings: Include critical/high code review findings in feedback.
        max_raw_chars: Cap raw output length in the feedback dict.

    Returns:
        Dict with keys: message (str), test_failures (bool), coverage_shortfall (bool),
        failed_count, error_count, line_coverage_pct, raw_output (truncated),
        findings_summary (if include_review_findings).
    """
    feedback: Dict[str, Any] = {
        "message": "",
        "test_failures": False,
        "coverage_shortfall": False,
        "failed_count": 0,
        "error_count": 0,
        "line_coverage_pct": None,
        "raw_output": "",
        "findings_summary": "",
    }
    parts: List[str] = []

    try:
        min_line = get_settings().guardrails.test_coverage_min
    except Exception:
        min_line = 0.8

    if output.test_run_result:
        r = output.test_run_result
        feedback["failed_count"] = r.failed
        feedback["error_count"] = r.errors
        feedback["line_coverage_pct"] = r.line_coverage_pct
        if r.raw_output:
            feedback["raw_output"] = r.raw_output[:max_raw_chars]

        if r.failed > 0 or r.errors > 0:
            feedback["test_failures"] = True
            parts.append(
                f"Tests: {r.failed} failed, {r.errors} errors, {r.passed} passed (total {r.total})."
            )
        if r.line_coverage_pct is not None:
            ratio = r.line_coverage_pct / 100.0 if r.line_coverage_pct > 1 else r.line_coverage_pct
            if ratio < min_line:
                feedback["coverage_shortfall"] = True
                parts.append(
                    f"Line coverage {r.line_coverage_pct}% is below required {min_line:.0%}. "
                    "Add or fix tests to meet the threshold."
                )
        if r.raw_output and (r.failed or r.errors):
            parts.append("Last output:\n" + r.raw_output[-1500:].replace("```", ""))

    if include_review_findings and output.code_review_report:
        rep = output.code_review_report
        if not rep.passed or rep.critical_count or rep.high_count:
            feedback["findings_summary"] = rep.summary or ""
            for f in rep.findings:
                if (f.severity or "").lower() in ("critical", "high"):
                    parts.append(
                        f"[{f.severity}] {f.title}: {f.description}. "
                        f"Recommendation: {f.recommendation or 'N/A'}"
                    )

    feedback["message"] = "\n".join(parts) if parts else "No specific feedback (run tests or review for details)."
    return feedback


__all__ = [
    "TestingCrewOutput",
    "create_testing_crew",
    "kickoff",
    "get_feedback",
]
