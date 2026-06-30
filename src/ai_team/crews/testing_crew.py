"""
Testing Crew: sequential test generation → execution → code review.

Single agent (QA Engineer), three tasks. Input: List[CodeFile] from Development Crew.
Output: TestRunResult + CodeReviewReport. Supports retry integration via get_feedback().
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from ai_team.agents.qa_engineer import create_qa_engineer
from ai_team.config.llm_factory import get_embedder_config
from ai_team.crews.memory_flag import crew_memory_enabled
from ai_team.config.settings import get_settings
from ai_team.models.development import CodeFile
from ai_team.models.qa_models import CodeReviewReport
from ai_team.tasks.testing_tasks import (
    code_review_task,
    test_execution_task,
    test_generation_task,
)
from ai_team.tools.file_tools import write_file as safe_write_file, normalize_pytest_path
from ai_team.tools.test_tools import (
    TestRunResult,
    clear_verified_pytest_run,
    get_verified_pytest_run,
    run_pytest_discover_workspace,
)
from crewai import Crew, Process
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# -----------------------------------------------------------------------------
# Output model (TestRunResult + CodeReviewReport)
# -----------------------------------------------------------------------------


class TestingCrewOutput(BaseModel):
    """Result of the Testing Crew: test run and code review."""

    test_run_result: TestRunResult | None = Field(
        default=None,
        description="Structured test execution result (pass/fail, coverage).",
    )
    code_review_report: CodeReviewReport | None = Field(
        default=None,
        description="Structured code review with findings and severity.",
    )
    quality_gate_passed: bool = Field(
        default=False,
        description="True if tests pass, coverage meets threshold, and no critical/high findings.",
    )
    raw_outputs: list[str] = Field(
        default_factory=list,
        description="Raw task outputs in order [test_gen, test_exec, code_review] for debugging.",
    )


# -----------------------------------------------------------------------------
# Crew build and kickoff
# -----------------------------------------------------------------------------


def _code_files_to_summary(code_files: list[CodeFile], max_chars: int = 12000) -> str:
    """Serialize code files for crew input (path + content snippet)."""
    parts: list[str] = []
    total = 0
    for cf in code_files:
        block = f"--- {cf.path} ({cf.language}) ---\n{cf.content}\n"
        if total + len(block) > max_chars:
            parts.append(block[: max_chars - total] + "\n... (truncated)")
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts) if parts else "(no code files provided)"


def _parse_code_files_from_task_raw(raw: str) -> list[CodeFile]:
    """Best-effort parse of test generation task output into CodeFile objects."""
    if not raw or not raw.strip():
        return []
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return []
    items: list[dict[str, Any]] = []
    if isinstance(data, dict) and isinstance(data.get("files"), list):
        items = [i for i in data["files"] if isinstance(i, dict)]
    elif isinstance(data, list):
        items = [i for i in data if isinstance(i, dict)]
    files: list[CodeFile] = []
    for item in items:
        if "path" not in item or "content" not in item:
            continue
        try:
            files.append(
                CodeFile(**{k: v for k, v in item.items() if k in CodeFile.model_fields})
            )
        except (TypeError, ValueError):
            continue
    return files


def _persist_test_files_from_code_files(code_files: list[CodeFile]) -> int:
    """Write test files from Development Crew output before QA runs."""
    written = 0
    for cf in code_files:
        if "test" not in cf.path.lower():
            continue
        try:
            safe_write_file(normalize_pytest_path(cf.path), cf.content)
            written += 1
        except Exception as exc:
            logger.warning(
                "testing_crew_dev_test_write_failed",
                path=cf.path,
                error=str(exc),
            )
    if written:
        logger.info("testing_crew_dev_tests_persisted", count=written)
    return written


def _persist_test_files_from_generation(raw: str) -> int:
    """Write test files from QA test_generation output to the workspace."""
    written = 0
    for cf in _parse_code_files_from_task_raw(raw):
        if "test" not in cf.path.lower():
            continue
        try:
            safe_write_file(normalize_pytest_path(cf.path), cf.content)
            written += 1
        except Exception as exc:
            logger.warning("testing_crew_test_write_failed", path=cf.path, error=str(exc))
    if written:
        logger.info("testing_crew_tests_persisted", count=written)
    return written


def _parse_task_output_as_model(raw: Any, model: type[BaseModel]) -> BaseModel | None:
    """Parse task raw output (str or object with .raw) into a Pydantic model."""
    text: str | None = None
    if isinstance(raw, str):
        text = raw
    elif hasattr(raw, "raw"):
        text = raw.raw or ""
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
    test_run_result: TestRunResult | None,
    code_review_report: CodeReviewReport | None,
    min_line_coverage: float,
    min_branch_coverage: float | None,
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


def _run_orchestrated_pytest() -> TestRunResult | None:
    """Run pytest in-process when the QA agent skips ``run_pytest`` (eval reliability)."""
    result = run_pytest_discover_workspace()
    if result is not None:
        logger.info(
            "testing_crew_orchestrated_pytest",
            passed=result.passed,
            failed=result.failed,
            success=result.success,
        )
    return result


def create_testing_crew(
    qa_agent: Any | None = None,
    guardrail_max_retries: int | None = None,
    memory: bool | None = None,
    verbose: bool = False,
    step_callback: Any | None = None,
    task_callback: Any | None = None,
    min_coverage_pct: float | None = None,
    agent_test_execution: bool = False,
) -> Crew:
    """
    Build the Testing Crew: sequential process, QA Engineer only.

    Tasks: test_generation → (optional agent test_execution) → code_review.
    By default pytest is orchestrated in ``kickoff()`` after generation — the agent
    ``test_execution`` task is skipped because OpenRouter models often omit ``run_pytest``
    and guardrail retries exhaust with empty LLM responses.
    """
    agent = qa_agent if qa_agent is not None else create_qa_engineer()
    if memory is None:
        memory = crew_memory_enabled()
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
    tasks: list[Any] = [t_gen]
    task_names = ["test_generation"]
    if agent_test_execution:
        t_exec = test_execution_task(
            agent,
            context=[t_gen],
            guardrail_max_retries=retries,
            min_coverage_pct=min_coverage_pct,
        )
        tasks.append(t_exec)
        task_names.append("test_execution")
        review_context = [t_gen, t_exec]
    else:
        review_context = [t_gen]

    t_review = code_review_task(
        agent,
        context=review_context,
        guardrail_max_retries=retries,
    )
    tasks.append(t_review)
    task_names.append("code_review")

    crew = Crew(
        agents=[agent],
        tasks=tasks,
        process=Process.sequential,
        memory=memory,
        embedder=get_embedder_config() if memory else None,
        verbose=verbose,
        step_callback=step_callback,
        task_callback=task_callback,
    )
    logger.info(
        "testing_crew_created",
        process="sequential",
        memory=memory,
        agent_test_execution=agent_test_execution,
        tasks=task_names,
    )
    return crew


def kickoff(
    code_files: list[CodeFile],
    qa_agent: Any | None = None,
    guardrail_max_retries: int | None = None,
    memory: bool | None = None,
    verbose: bool = False,
    step_callback: Any | None = None,
    task_callback: Any | None = None,
    min_coverage_pct: float | None = None,
    agent_test_execution: bool = False,
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
    clear_verified_pytest_run()
    _persist_test_files_from_code_files(code_files)

    crew = create_testing_crew(
        qa_agent=qa_agent,
        guardrail_max_retries=guardrail_max_retries,
        memory=memory,
        verbose=verbose,
        step_callback=step_callback,
        task_callback=task_callback,
        min_coverage_pct=min_coverage_pct,
        agent_test_execution=agent_test_execution,
    )
    code_files_summary = _code_files_to_summary(code_files)
    inputs = {"code_files_summary": code_files_summary}

    raw_outputs: list[str] = []
    crew_result: Any = None
    try:
        crew_result = crew.kickoff(inputs=inputs)
    except Exception as exc:
        logger.warning(
            "testing_crew_kickoff_failed",
            error=str(exc),
            reason="continuing with orchestrated pytest salvage",
        )

    if crew_result is not None:
        if getattr(crew_result, "tasks_output", None):
            for out in crew_result.tasks_output:
                raw = out.raw if hasattr(out, "raw") else str(out)
                raw_outputs.append(raw)
        elif hasattr(crew_result, "raw"):
            raw_outputs.append(crew_result.raw or "")

    if raw_outputs:
        _persist_test_files_from_generation(raw_outputs[0])

    test_run_result: TestRunResult | None = get_verified_pytest_run()
    if test_run_result is None:
        test_run_result = _run_orchestrated_pytest()
        if test_run_result is None:
            logger.warning(
                "testing_crew_no_verified_pytest",
                reason="run_pytest not called and no tests found",
            )

    code_review_report: CodeReviewReport | None = None
    review_idx = 2 if agent_test_execution else 1
    if len(raw_outputs) > review_idx:
        code_review_report = _parse_task_output_as_model(raw_outputs[review_idx], CodeReviewReport)

    min_line = 0.8
    min_branch: float | None = None
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
) -> dict[str, Any]:
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
    feedback: dict[str, Any] = {
        "message": "",
        "test_failures": False,
        "coverage_shortfall": False,
        "failed_count": 0,
        "error_count": 0,
        "line_coverage_pct": None,
        "raw_output": "",
        "findings_summary": "",
    }
    parts: list[str] = []

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

    feedback["message"] = (
        "\n".join(parts) if parts else "No specific feedback (run tests or review for details)."
    )
    return feedback


__all__ = [
    "TestingCrewOutput",
    "create_testing_crew",
    "kickoff",
    "get_feedback",
]
