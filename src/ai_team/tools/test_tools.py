"""
Testing tools: pytest runner with coverage, single-test runner, coverage reports, lint, test quality.

Used by the QA agent to run tests, collect coverage, run lint, and validate test code quality.
"""

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)

# Retry config for flaky tests: run up to 2 times on failure
FLAKY_RETRY_ATTEMPTS = 2


# -----------------------------------------------------------------------------
# Pydantic result models
# -----------------------------------------------------------------------------


class CoverageSummary(BaseModel):
    """Per-file coverage breakdown."""

    file_path: str = Field(..., description="Source file path.")
    line_coverage_pct: float = Field(..., description="Line coverage percentage.")
    branch_coverage_pct: Optional[float] = Field(None, description="Branch coverage percentage if available.")
    lines_covered: int = Field(0, description="Lines covered.")
    lines_missing: int = Field(0, description="Lines not covered.")


class TestRunResult(BaseModel):
    """Structured result of a full pytest run with coverage."""

    total: int = Field(..., description="Total number of tests.")
    passed: int = Field(..., description="Number of passed tests.")
    failed: int = Field(0, description="Number of failed tests.")
    errors: int = Field(0, description="Number of test errors.")
    skipped: int = Field(0, description="Number of skipped tests.")
    warnings: int = Field(0, description="Number of warnings.")
    duration_seconds: float = Field(0.0, description="Total run duration in seconds.")
    line_coverage_pct: Optional[float] = Field(None, description="Overall line coverage percentage.")
    branch_coverage_pct: Optional[float] = Field(None, description="Overall branch coverage percentage.")
    per_file_coverage: List[CoverageSummary] = Field(default_factory=list, description="Per-file coverage.")
    raw_output: str = Field("", description="Raw pytest/cov output for debugging.")
    success: bool = Field(..., description="True if all tests passed and no errors.")


class TestResult(BaseModel):
    """Result of running a single test (e.g. for debugging)."""

    test_file: str = Field(..., description="Test file path.")
    test_name: str = Field(..., description="Test function or node id.")
    passed: bool = Field(..., description="Whether the test passed.")
    duration_seconds: float = Field(0.0, description="Duration in seconds.")
    traceback: str = Field("", description="Full traceback on failure.")
    raw_output: str = Field("", description="Raw pytest output.")


class UncoveredRegion(BaseModel):
    """Uncovered lines or branches in a file."""

    file_path: str = Field(..., description="Source file path.")
    line_start: int = Field(..., description="Start line number.")
    line_end: Optional[int] = Field(None, description="End line number (for ranges).")
    branch_info: Optional[str] = Field(None, description="Branch description if applicable.")


class CoverageReport(BaseModel):
    """Coverage report with HTML/JSON paths and suggestions."""

    html_report_path: Optional[str] = Field(None, description="Path to HTML coverage report.")
    json_report_path: Optional[str] = Field(None, description="Path to JSON coverage report.")
    line_coverage_pct: float = Field(0.0, description="Overall line coverage.")
    branch_coverage_pct: Optional[float] = Field(None, description="Overall branch coverage.")
    uncovered_lines: List[UncoveredRegion] = Field(default_factory=list, description="Uncovered line regions.")
    uncovered_branches: List[UncoveredRegion] = Field(default_factory=list, description="Uncovered branches.")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions for tests to add.")
    raw_summary: str = Field("", description="Short summary text.")


class LintIssue(BaseModel):
    """Single lint finding."""

    file_path: str = Field(..., description="File path.")
    line: Optional[int] = Field(None, description="Line number.")
    column: Optional[int] = Field(None, description="Column number.")
    code: str = Field("", description="Rule or error code.")
    message: str = Field(..., description="Message.")
    severity: str = Field("error", description="One of: error, warning, info.")
    tool: str = Field("ruff", description="Tool that produced the issue: ruff or mypy.")


class LintReport(BaseModel):
    """Aggregated lint results from ruff and mypy."""

    issues: List[LintIssue] = Field(default_factory=list, description="All lint issues.")
    error_count: int = Field(0, description="Number of errors.")
    warning_count: int = Field(0, description="Number of warnings.")
    info_count: int = Field(0, description="Number of info-level issues.")
    success: bool = Field(..., description="True if no errors.")
    raw_output: str = Field("", description="Combined raw output from tools.")


class TestQualityReport(BaseModel):
    """Result of validating test code quality."""

    has_assertions: bool = Field(..., description="Whether the test contains assertions.")
    meaningful_names: bool = Field(..., description="Whether test names follow conventions.")
    no_hardcoded_values: bool = Field(..., description="No obvious hardcoded magic values.")
    has_setup_teardown: bool = Field(..., description="Uses setup/teardown or fixtures where appropriate.")
    edge_cases_mentioned: bool = Field(..., description="Hints of edge-case coverage (e.g. empty, None).")
    issues: List[str] = Field(default_factory=list, description="List of specific issues found.")
    score_notes: str = Field("", description="Short summary and recommendations.")
    passed: bool = Field(..., description="Overall quality check passed.")


# -----------------------------------------------------------------------------
# Core functions (return Pydantic models)
# -----------------------------------------------------------------------------


def _parse_pytest_summary(stdout: str, stderr: str) -> Dict[str, Any]:
    """Parse pytest -v output for counts and duration."""
    combined = stdout + "\n" + stderr
    total = passed = failed = errors = skipped = warnings = 0
    duration_seconds = 0.0

    # e.g. "3 passed in 0.12s" or "2 failed, 1 passed in 0.45s" or "1 error in 0.10s"
    summary_match = re.search(
        r"(?:(\d+)\s+passed)?\s*(?:(\d+)\s+failed)?\s*(?:(\d+)\s+error(?:s)?)?\s*(?:(\d+)\s+skipped)?\s*(?:in\s+([\d.]+)\s*s)?",
        combined,
        re.IGNORECASE,
    )
    if summary_match:
        g = summary_match.groups()
        passed = int(g[0] or 0)
        failed = int(g[1] or 0)
        errors = int(g[2] or 0)
        skipped = int(g[3] or 0)
        if g[4]:
            duration_seconds = float(g[4])

    # Warnings: "X warnings" or "X passed, Y warnings"
    warn_match = re.search(r"(\d+)\s+warnings?", combined, re.IGNORECASE)
    if warn_match:
        warnings = int(warn_match.group(1))

    total = passed + failed + errors + skipped
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "warnings": warnings,
        "duration_seconds": duration_seconds,
    }


def _parse_coverage_terminal(stdout: str) -> Dict[str, Any]:
    """Parse coverage report from terminal (e.g. pytest-cov --cov-report=term)."""
    line_pct: Optional[float] = None
    branch_pct: Optional[float] = None
    per_file: List[CoverageSummary] = []

    # TOTAL line: "TOTAL    120   45   62%"
    total_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", stdout)
    if total_match:
        line_pct = float(total_match.group(1))

    # Branch coverage: "TOTAL ... 45%"
    branch_match = re.search(r"(\d+)%\s*$", stdout, re.MULTILINE)
    if branch_match and "branch" in stdout.lower():
        branch_pct = float(branch_match.group(1))

    # Per-file: "src/ai_team/foo.py    10    5    50%"
    for line in stdout.splitlines():
        m = re.match(r"^([^\s]+\.py)\s+(\d+)\s+(\d+)\s+(\d+)%", line.strip())
        if m and "TOTAL" not in line:
            path, stmts, miss, pct = m.group(1), int(m.group(2)), int(m.group(3)), float(m.group(4))
            per_file.append(
                CoverageSummary(
                    file_path=path,
                    line_coverage_pct=pct,
                    lines_covered=stmts - miss,
                    lines_missing=miss,
                )
            )

    return {
        "line_coverage_pct": line_pct,
        "branch_coverage_pct": branch_pct,
        "per_file_coverage": per_file,
    }


def run_pytest(test_path: str, source_path: str) -> TestRunResult:
    """
    Execute pytest with coverage collection and return structured results.
    Retries once on failure (flaky test handling).
    """
    cwd = Path.cwd()
    test_dir = cwd / test_path if not Path(test_path).is_absolute() else Path(test_path)
    source_dir = cwd / source_path if not Path(source_path).is_absolute() else Path(source_path)
    if not source_dir.exists():
        source_dir = cwd / "src" / "ai_team"

    cmd = [
        "python",
        "-m",
        "pytest",
        str(test_dir),
        "-v",
        "--tb=short",
        f"--cov={source_dir}",
        "--cov-report=term-missing",
        "--cov-branch",
        "-q",
    ]
    raw_output = ""
    last_summary: Dict[str, Any] = {}
    last_cov: Dict[str, Any] = {}

    for attempt in range(FLAKY_RETRY_ATTEMPTS):
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            raw_output = proc.stdout + "\n" + proc.stderr
            last_summary = _parse_pytest_summary(proc.stdout, proc.stderr)
            last_cov = _parse_coverage_terminal(raw_output)
            # If all passed, no need to retry
            if last_summary.get("failed", 0) == 0 and last_summary.get("errors", 0) == 0:
                break
        except subprocess.TimeoutExpired:
            last_summary = {"total": 0, "passed": 0, "failed": 0, "errors": 1, "skipped": 0, "warnings": 0, "duration_seconds": 300.0}
            raw_output = "pytest timed out after 300s"
            break
        except Exception as e:
            last_summary = {"total": 0, "passed": 0, "failed": 0, "errors": 1, "skipped": 0, "warnings": 0, "duration_seconds": 0.0}
            raw_output = str(e)
            break

    success = (last_summary.get("failed", 0) == 0 and last_summary.get("errors", 0) == 0)
    return TestRunResult(
        total=last_summary.get("total", 0),
        passed=last_summary.get("passed", 0),
        failed=last_summary.get("failed", 0),
        errors=last_summary.get("errors", 0),
        skipped=last_summary.get("skipped", 0),
        warnings=last_summary.get("warnings", 0),
        duration_seconds=last_summary.get("duration_seconds", 0.0),
        line_coverage_pct=last_cov.get("line_coverage_pct"),
        branch_coverage_pct=last_cov.get("branch_coverage_pct"),
        per_file_coverage=last_cov.get("per_file_coverage", []),
        raw_output=raw_output[:4096],
        success=success,
    )


def run_specific_test(test_file: str, test_name: str) -> TestResult:
    """
    Run a single test function for debugging. Includes full traceback on failure.
    Retries once on failure (flaky test handling).
    """
    cwd = Path.cwd()
    path = cwd / test_file if not Path(test_file).is_absolute() else Path(test_file)
    node_id = f"{path}::{test_name}" if "::" not in test_name else f"{path}::{test_name}"

    cmd = ["python", "-m", "pytest", node_id, "-v", "--tb=long", "-q"]
    raw_output = ""
    passed = False
    duration_seconds = 0.0
    traceback = ""

    for attempt in range(FLAKY_RETRY_ATTEMPTS):
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            raw_output = proc.stdout + "\n" + proc.stderr
            passed = proc.returncode == 0
            if "FAILED" in raw_output or "ERROR" in raw_output:
                # Extract traceback: from "FAILED ..." or "E   ..." lines
                lines = raw_output.splitlines()
                tb_lines = []
                in_tb = False
                for line in lines:
                    if "FAILED" in line or "Error" in line or line.strip().startswith("E "):
                        in_tb = True
                    if in_tb:
                        tb_lines.append(line)
                traceback = "\n".join(tb_lines) if tb_lines else raw_output
            # Duration: "0.12s" in "passed in 0.12s"
            dur_match = re.search(r"in\s+([\d.]+)\s*s", raw_output)
            if dur_match:
                duration_seconds = float(dur_match.group(1))
            if passed:
                break
        except subprocess.TimeoutExpired:
            raw_output = "Test timed out after 120s"
            traceback = raw_output
            break
        except Exception as e:
            raw_output = str(e)
            traceback = str(e)
            break

    return TestResult(
        test_file=test_file,
        test_name=test_name,
        passed=passed,
        duration_seconds=duration_seconds,
        traceback=traceback[:2048],
        raw_output=raw_output[:4096],
    )


def generate_coverage_report(source_path: str) -> CoverageReport:
    """
    Generate HTML and JSON coverage reports; identify uncovered lines/branches and suggest tests.
    """
    cwd = Path.cwd()
    source_dir = cwd / source_path if not Path(source_path).is_absolute() else Path(source_path)
    if not source_dir.exists():
        source_dir = cwd / "src" / "ai_team"
    out_dir = cwd / "coverage_report"
    out_dir.mkdir(exist_ok=True)
    html_path = out_dir / "html"
    json_path = out_dir / "coverage.json"

    # Run coverage over tests (assume tests/ exists)
    run_cmd = ["python", "-m", "coverage", "run", "--source", str(source_dir), "-m", "pytest", "tests", "-q", "--tb=no"]
    subprocess.run(run_cmd, cwd=cwd, capture_output=True, timeout=300, check=False)

    report_cmd = ["python", "-m", "coverage", "report", "--show-missing", "--skip-empty"]
    proc = subprocess.run(report_cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
    raw_summary = proc.stdout or ""

    html_cmd = ["python", "-m", "coverage", "html", "-d", str(html_path)]
    subprocess.run(html_cmd, cwd=cwd, capture_output=True, timeout=60)

    json_cmd = ["python", "-m", "coverage", "json", "-o", str(json_path)]
    subprocess.run(json_cmd, cwd=cwd, capture_output=True, timeout=60)

    # Parse summary for overall %
    line_pct = 0.0
    branch_pct: Optional[float] = None
    total_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", raw_summary)
    if total_match:
        line_pct = float(total_match.group(1))

    uncovered_lines: List[UncoveredRegion] = []
    uncovered_branches: List[UncoveredRegion] = []
    suggestions: List[str] = []

    # Per-line missing from "missing" column: "1-5, 10"
    for line in raw_summary.splitlines():
        if ".py" in line and "TOTAL" not in line:
            parts = line.split()
            if len(parts) >= 4:
                file_path = parts[0]
                missing = parts[3] if len(parts) > 3 else ""
                if missing and missing != "-":
                    for part in missing.split(","):
                        part = part.strip()
                        if "-" in part:
                            a, b = part.split("-", 1)
                            try:
                                uncovered_lines.append(
                                    UncoveredRegion(file_path=file_path, line_start=int(a), line_end=int(b))
                                )
                            except ValueError:
                                pass
                        else:
                            try:
                                uncovered_lines.append(UncoveredRegion(file_path=file_path, line_start=int(part)))
                            except ValueError:
                                pass

    # Suggestions based on uncovered files/lines
    if uncovered_lines:
        files_with_missing = list({u.file_path for u in uncovered_lines})
        suggestions.append(f"Add tests for: {', '.join(files_with_missing[:5])}.")
    if line_pct < 80:
        suggestions.append("Increase line coverage (e.g. add unit tests for main branches and edge cases).")
    if not suggestions:
        suggestions.append("Coverage looks good; consider adding branch coverage for critical paths.")

    return CoverageReport(
        html_report_path=str(html_path) if (html_path / "index.html").exists() else None,
        json_report_path=str(json_path) if json_path.exists() else None,
        line_coverage_pct=line_pct,
        branch_coverage_pct=branch_pct,
        uncovered_lines=uncovered_lines,
        uncovered_branches=uncovered_branches,
        suggestions=suggestions,
        raw_summary=raw_summary[:1024],
    )


def run_lint(source_path: str) -> LintReport:
    """Run ruff and mypy on Python files under source_path; aggregate results by severity."""
    cwd = Path.cwd()
    src = cwd / source_path if not Path(source_path).is_absolute() else Path(source_path)
    if not src.exists():
        src = cwd / "src" / "ai_team"

    issues: List[LintIssue] = []
    raw_parts: List[str] = []

    # Ruff
    ruff_cmd = ["python", "-m", "ruff", "check", str(src), "--output-format=concise"]
    proc = subprocess.run(ruff_cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
    ruff_out = proc.stdout or proc.stderr or ""
    raw_parts.append("=== ruff ===\n" + ruff_out)
    for line in ruff_out.splitlines():
        if not line.strip():
            continue
        # "path:line:col: code message"
        m = re.match(r"^([^:]+):(\d+):(\d+):\s*([A-Z]\d+)\s+(.+)", line)
        if m:
            path, line_no, col, code, msg = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4), m.group(5)
            severity = "warning" if code.startswith("W") or code.startswith("N") else "error"
            issues.append(
                LintIssue(file_path=path, line=line_no, column=col, code=code, message=msg, severity=severity, tool="ruff")
            )

    # Mypy
    mypy_cmd = ["python", "-m", "mypy", str(src), "--no-error-summary"]
    proc = subprocess.run(mypy_cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    mypy_out = proc.stdout or proc.stderr or ""
    raw_parts.append("=== mypy ===\n" + mypy_out)
    for line in mypy_out.splitlines():
        if "error:" in line or "note:" in line:
            m = re.match(r"^([^:]+):(\d+):\s*(?:error|note):\s*(.+)", line)
            if m:
                path, line_no, msg = m.group(1), int(m.group(2)), m.group(3)
                severity = "info" if "note:" in line else "error"
                issues.append(
                    LintIssue(file_path=path, line=line_no, message=msg, severity=severity, tool="mypy")
                )

    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    return LintReport(
        issues=issues,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        success=(error_count == 0),
        raw_output="\n".join(raw_parts)[:8192],
    )


def validate_test_quality(test_code: str) -> TestQualityReport:
    """
    Check test code for: assertions, meaningful names, no hardcoded values, setup/teardown, edge cases.
    """
    issues: List[str] = []
    has_assertions = "assert " in test_code or "assert_" in test_code or "assertEqual" in test_code or "assertTrue" in test_code
    if not has_assertions:
        issues.append("No assertions found; test should assert expected behavior.")

    # Meaningful names: test_* or test_*_
    meaningful_names = bool(re.search(r"def\s+test_[a-z0-9_]+", test_code))
    if not meaningful_names:
        issues.append("Test names should follow test_<description> pattern.")

    # Hardcoded: magic numbers or strings that look like literals in asserts
    magic = re.findall(r"assert.*\b(?:==|!=|>|<)\s*[\d']{2,}", test_code)
    no_hardcoded = len(magic) <= 1  # one literal in assert is ok
    if not no_hardcoded:
        issues.append("Consider extracting magic numbers/strings into named constants or fixtures.")

    # Setup/teardown or fixtures
    has_setup_teardown = (
        "setUp" in test_code or "teardown" in test_code.lower() or "fixture" in test_code.lower() or "@pytest.fixture" in test_code
    )
    if not has_setup_teardown and len(test_code) > 500:
        issues.append("Long test file may benefit from setup/teardown or fixtures.")

    # Edge cases: empty, None, zero, etc.
    edge_cases_mentioned = any(
        x in test_code.lower() for x in ["empty", "none", "zero", "null", "edge", "boundary", "invalid", "raise", "exception"]
    )

    passed = has_assertions and meaningful_names and len(issues) <= 2
    score_notes = (
        "Quality checks passed." if passed
        else "Issues: " + "; ".join(issues[:5]) + ". Consider adding assertions, clear names, and edge-case tests."
    )

    return TestQualityReport(
        has_assertions=has_assertions,
        meaningful_names=meaningful_names,
        no_hardcoded_values=no_hardcoded,
        has_setup_teardown=has_setup_teardown,
        edge_cases_mentioned=edge_cases_mentioned,
        issues=issues,
        score_notes=score_notes,
        passed=passed,
    )


# -----------------------------------------------------------------------------
# Tool input schemas (for CrewAI)
# -----------------------------------------------------------------------------


class RunPytestInput(BaseModel):
    test_path: str = Field(..., description="Path to test directory or file (e.g. tests/unit).")
    source_path: str = Field(..., description="Path to source for coverage (e.g. src/ai_team).")


class RunSpecificTestInput(BaseModel):
    test_file: str = Field(..., description="Test file path (e.g. tests/unit/tools/test_test_tools.py).")
    test_name: str = Field(..., description="Test function name or node id (e.g. test_run_pytest).")


class GenerateCoverageReportInput(BaseModel):
    source_path: str = Field(..., description="Path to source to measure (e.g. src/ai_team).")


class RunLintInput(BaseModel):
    source_path: str = Field(..., description="Path to source to lint (e.g. src/ai_team).")


class ValidateTestQualityInput(BaseModel):
    test_code: str = Field(..., description="The test code string to validate.")


# -----------------------------------------------------------------------------
# CrewAI tools (wrap functions for agent use)
# -----------------------------------------------------------------------------


class RunPytestTool(BaseTool):
    """Run pytest with coverage on a test path and source path; returns structured summary. Retries once on failure."""

    name: str = "run_pytest"
    description: str = (
        "Execute pytest with coverage. Provide test_path (e.g. tests/unit) and source_path (e.g. src/ai_team). "
        "Returns total/passed/failed/errors, duration, line and branch coverage, and per-file breakdown. "
        "Flaky tests are retried once."
    )
    args_schema: Type[BaseModel] = RunPytestInput

    def _run(self, test_path: str, source_path: str) -> str:
        result = run_pytest(test_path, source_path)
        return result.model_dump_json(indent=2)


class RunSpecificTestTool(BaseTool):
    """Run a single test by file and name for debugging; includes full traceback on failure. Retries once on failure."""

    name: str = "run_specific_test"
    description: str = (
        "Run one test: test_file (e.g. tests/unit/tools/test_test_tools.py) and test_name (e.g. test_run_pytest). "
        "Returns passed/failed, duration, and full traceback on failure. Retries once on failure."
    )
    args_schema: Type[BaseModel] = RunSpecificTestInput

    def _run(self, test_file: str, test_name: str) -> str:
        result = run_specific_test(test_file, test_name)
        return result.model_dump_json(indent=2)


class GenerateCoverageReportTool(BaseTool):
    """Generate HTML and JSON coverage reports; list uncovered lines and suggest tests to add."""

    name: str = "generate_coverage_report"
    description: str = (
        "Generate coverage report for source_path (e.g. src/ai_team). Produces HTML and JSON reports, "
        "lists uncovered lines/branches, and suggests what tests to add."
    )
    args_schema: Type[BaseModel] = GenerateCoverageReportInput

    def _run(self, source_path: str) -> str:
        result = generate_coverage_report(source_path)
        return result.model_dump_json(indent=2)


class RunLintTool(BaseTool):
    """Run ruff and mypy on Python files; returns aggregated issues by severity."""

    name: str = "run_lint"
    description: str = (
        "Run ruff and mypy on source_path (e.g. src/ai_team). Returns list of issues with file, line, code, "
        "message, and severity (error/warning/info)."
    )
    args_schema: Type[BaseModel] = RunLintInput

    def _run(self, source_path: str) -> str:
        result = run_lint(source_path)
        return result.model_dump_json(indent=2)


class ValidateTestQualityTool(BaseTool):
    """Validate test code quality: assertions, names, hardcoded values, setup/teardown, edge cases."""

    name: str = "validate_test_quality"
    description: str = (
        "Validate test code (string). Checks: assertions present, meaningful test names, no hardcoded values, "
        "proper setup/teardown, edge cases covered. Returns quality report with issues and recommendations."
    )
    args_schema: Type[BaseModel] = ValidateTestQualityInput

    def _run(self, test_code: str) -> str:
        result = validate_test_quality(test_code)
        return result.model_dump_json(indent=2)


def get_test_tools() -> List[BaseTool]:
    """Return the list of testing tools for the QA agent."""
    return [
        RunPytestTool(),
        RunSpecificTestTool(),
        GenerateCoverageReportTool(),
        RunLintTool(),
        ValidateTestQualityTool(),
    ]
