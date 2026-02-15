"""
QA Engineer tools: test generation persistence, test runner, coverage analyzer,
bug reporter, and lint runner. Used by the QA Engineer agent for test automation
and quality gates.
"""

import subprocess
from pathlib import Path
from typing import Any, List, Optional

from crewai.tools import tool

from ai_team.config.settings import get_settings

# Default minimum coverage for guardrail (generated code >80%)
QA_MIN_COVERAGE_DEFAULT = 0.8


def _workspace_root() -> Path:
    """Return workspace root from settings, resolved and created if needed."""
    root = Path(get_settings().project.workspace_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_path(relative_path: str) -> Path:
    """Resolve path under workspace; prevent path traversal."""
    root = _workspace_root()
    path = (root / relative_path).resolve()
    if not str(path).startswith(str(root)):
        raise ValueError(f"Path must be under workspace: {relative_path}")
    return path


# -----------------------------------------------------------------------------
# Test generator (writes test file; agent generates content from source analysis)
# -----------------------------------------------------------------------------


@tool("Generate and persist a test file from path and content")
def test_generator(file_path: str, content: str) -> str:
    """
    Write a test file to the given path under the workspace. Use after analyzing
    source code to produce unit tests (pytest), integration tests, or fixtures.
    Path is relative to workspace (e.g. 'tests/test_foo.py').

    Args:
        file_path: Relative path for the test file under workspace.
        content: Full content of the test file to write.
    """
    try:
        path = _safe_path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Wrote test file: {path} ({len(content)} chars)"
    except Exception as e:
        return f"Error writing test file: {e}"


# -----------------------------------------------------------------------------
# Test runner (pytest)
# -----------------------------------------------------------------------------


@tool("Run pytest in a directory or on specific paths")
def test_runner(
    target: str = ".",
    extra_args: Optional[str] = None,
) -> str:
    """
    Run pytest in the workspace. Use to execute unit or integration tests.

    Args:
        target: Directory or file path relative to workspace (default: '.').
        extra_args: Optional extra pytest args (e.g. '-v -x').
    """
    root = _workspace_root()
    work_dir = root / target if target != "." else root
    if not work_dir.is_dir():
        work_dir = _safe_path(target)
        if work_dir.is_dir():
            pass
        else:
            work_dir = work_dir.parent
    cmd: List[str] = ["pytest", str(work_dir), "-v", "--tb=short"]
    if extra_args:
        cmd.extend(extra_args.strip().split())
    try:
        result = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        out = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            out += f"\n[Exit code: {result.returncode}]"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: pytest timed out after 300s"
    except FileNotFoundError:
        return "Error: pytest not found. Install with: pip install pytest"
    except Exception as e:
        return f"Error running pytest: {e}"


# -----------------------------------------------------------------------------
# Coverage analyzer (pytest-cov)
# -----------------------------------------------------------------------------


@tool("Run coverage (pytest-cov) and return line/branch report")
def coverage_analyzer(
    source: str = ".",
    test_target: str = ".",
) -> str:
    """
    Run pytest with coverage and return a coverage report (line and branch).
    Use to check if code meets the minimum coverage threshold (e.g. 80%).

    Args:
        source: Comma-separated paths or package names to measure (default: '.').
        test_target: Directory or file to run tests from (default: '.').
    """
    root = _workspace_root()
    work_dir = root / test_target if test_target != "." else root
    if not work_dir.is_dir():
        work_dir = root
    cov_sources = [s.strip() for s in source.split(",") if s.strip()]
    cov_args = [f"--cov={s}" for s in cov_sources] if cov_sources else ["--cov=."]
    cmd = [
        "pytest",
        str(work_dir),
        "-v",
        *cov_args,
        "--cov-report=term-missing",
        "--cov-branch",
        "--tb=short",
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        out = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            out += f"\n[Exit code: {result.returncode}]"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: coverage run timed out after 300s"
    except FileNotFoundError:
        return "Error: pytest or pytest-cov not found. Install with: pip install pytest pytest-cov"
    except Exception as e:
        return f"Error running coverage: {e}"


# -----------------------------------------------------------------------------
# Bug reporter (record for feedback to developers)
# -----------------------------------------------------------------------------


@tool("Record a bug report with severity and reproduction steps")
def bug_reporter(
    title: str,
    severity: str,
    reproduction_steps: str,
    expected_behavior: str = "",
    actual_behavior: str = "",
    file_path: str = "",
) -> str:
    """
    Record a bug for feedback to developer agents. Use when tests fail or
    you find a defect. Severity should be one of: critical, high, medium, low.

    Args:
        title: Short bug title.
        severity: critical, high, medium, or low.
        reproduction_steps: Steps to reproduce.
        expected_behavior: What should happen.
        actual_behavior: What actually happens.
        file_path: Optional file or module path.
    """
    sev = severity.lower()
    if sev not in ("critical", "high", "medium", "low"):
        sev = "medium"
    summary = (
        f"Bug recorded: {title}\n"
        f"Severity: {sev}\n"
        f"Reproduction: {reproduction_steps}\n"
    )
    if expected_behavior:
        summary += f"Expected: {expected_behavior}\n"
    if actual_behavior:
        summary += f"Actual: {actual_behavior}\n"
    if file_path:
        summary += f"File: {file_path}\n"
    return summary + "\n(Use this in feedback_for_developers when tests fail.)"


# -----------------------------------------------------------------------------
# Lint runner (ruff)
# -----------------------------------------------------------------------------


@tool("Run linter (ruff) on a path and return issues")
def lint_runner(path: str = ".") -> str:
    """
    Run ruff linter on the given path under workspace. Use to check code
    quality before or after tests.

    Args:
        path: Directory or file relative to workspace (default: '.').
    """
    root = _workspace_root()
    target = _safe_path(path) if path != "." else root
    cmd = ["ruff", "check", str(target), "--output-format=concise"]
    try:
        result = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = (result.stdout or "").strip() + (result.stderr or "").strip()
        if result.returncode == 0 and not out:
            return "No lint issues found."
        return out or f"(ruff exit code: {result.returncode})"
    except subprocess.TimeoutExpired:
        return "Error: ruff timed out after 60s"
    except FileNotFoundError:
        return "Error: ruff not found. Install with: pip install ruff"
    except Exception as e:
        return f"Error running lint: {e}"


def get_qa_tools() -> List[Any]:
    """Return the list of QA tools for the QA Engineer agent."""
    return [
        test_generator,
        test_runner,
        coverage_analyzer,
        bug_reporter,
        lint_runner,
    ]
