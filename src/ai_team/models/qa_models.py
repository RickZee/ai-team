"""Pydantic models for QA Engineer agent output (TestResult, coverage, bug reports)."""

from typing import List

from pydantic import BaseModel, Field


class GeneratedTestFile(BaseModel):
    """A generated test file with path and content."""

    path: str = Field(..., description="Relative or absolute path to the test file")
    content: str = Field(..., description="Full file content")


class TestExecutionResult(BaseModel):
    """Result of running a test or test suite."""

    passed: int = Field(0, description="Number of tests passed")
    failed: int = Field(0, description="Number of tests failed")
    errors: int = Field(0, description="Number of errors (e.g. collection/setup)")
    skipped: int = Field(0, description="Number of tests skipped")
    total: int = Field(0, description="Total tests run")
    output: str = Field("", description="Raw test runner output (e.g. pytest stdout)")
    failed_tests: List[str] = Field(
        default_factory=list,
        description="Identifiers or names of failed tests",
    )


class FileCoverage(BaseModel):
    """Per-file coverage breakdown."""

    path: str = Field(..., description="Source file path")
    line_coverage: float = Field(0.0, ge=0, le=1, description="Line coverage ratio 0-1")
    branch_coverage: float = Field(0.0, ge=0, le=1, description="Branch coverage ratio 0-1")
    lines_covered: int = Field(0, description="Number of lines covered")
    lines_missing: int = Field(0, description="Number of lines not covered")


class CoverageReport(BaseModel):
    """Overall and per-file coverage report."""

    line_coverage: float = Field(0.0, ge=0, le=1, description="Overall line coverage ratio")
    branch_coverage: float = Field(0.0, ge=0, le=1, description="Overall branch coverage ratio")
    per_file: List[FileCoverage] = Field(
        default_factory=list,
        description="Per-file coverage breakdown",
    )
    raw_output: str = Field("", description="Raw coverage tool output (e.g. pytest-cov)")


class BugReport(BaseModel):
    """A single bug report with severity and reproduction steps."""

    title: str = Field(..., description="Short bug title")
    severity: str = Field(..., description="e.g. critical, high, medium, low")
    reproduction_steps: str = Field(..., description="Steps to reproduce the bug")
    expected: str = Field("", description="Expected behavior")
    actual: str = Field("", description="Actual behavior")
    file_path: str = Field("", description="Relevant file or module if applicable")
    line_number: int = Field(0, description="Line number if applicable")


class TestResult(BaseModel):
    """
    Structured output from the QA Engineer agent: generated tests,
    execution results, coverage, and bug reports. Used for quality gates
    (e.g. minimum coverage threshold, zero critical bugs).
    """

    test_files_generated: List[GeneratedTestFile] = Field(
        default_factory=list,
        description="Test files generated (path, content)",
    )
    execution_results: TestExecutionResult = Field(
        default_factory=TestExecutionResult,
        description="Test execution results (passed, failed, errors)",
    )
    coverage_report: CoverageReport = Field(
        default_factory=CoverageReport,
        description="Coverage report (line, branch, per-file breakdown)",
    )
    bug_reports: List[BugReport] = Field(
        default_factory=list,
        description="Bug reports with severity and reproduction steps",
    )
    quality_gate_passed: bool = Field(
        False,
        description="True if min coverage met and no critical bugs",
    )
    feedback_for_developers: str = Field(
        "",
        description="Actionable feedback for developer agents when tests fail or gates fail",
    )
