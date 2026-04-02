"""Unit tests for ``qa_tools`` (generator, runner, coverage, bug reporter, lint, factory)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ai_team.tools.qa_tools import (
    QA_MIN_COVERAGE_DEFAULT,
    bug_reporter,
    coverage_analyzer,
    get_qa_tools,
    lint_runner,
    test_generator,
    test_runner,
)


@pytest.fixture
def qa_workspace(tmp_path: Path) -> Path:
    """Patch workspace to a temp directory."""
    ws = tmp_path / "ws"
    ws.mkdir()
    mock_settings = MagicMock()
    mock_settings.project.workspace_dir = str(ws)
    with patch("ai_team.tools.qa_tools.get_settings", return_value=mock_settings):
        yield ws


class TestTestGenerator:
    def test_writes_file_under_workspace(self, qa_workspace: Path) -> None:
        out = test_generator.run(
            file_path="tests/test_foo.py",
            content="def test_ok():\n    assert True\n",
        )
        assert "Wrote test file" in out
        assert (qa_workspace / "tests" / "test_foo.py").exists()

    def test_path_traversal_returns_error(self, qa_workspace: Path) -> None:
        out = test_generator.run(file_path="../outside.py", content="x")
        assert "Error" in out


class TestTestRunner:
    def test_invokes_pytest_with_workspace_cwd(self, qa_workspace: Path) -> None:
        captured: dict[str, object] = {}

        def fake_run(cmd, cwd, capture_output, text, timeout):  # noqa: ANN001
            captured["cmd"] = cmd
            captured["cwd"] = cwd
            return MagicMock(returncode=0, stdout="1 passed\n", stderr="")

        with patch("ai_team.tools.qa_tools.subprocess.run", side_effect=fake_run):
            out = test_runner.run(target=".", extra_args=None)
        assert "1 passed" in out
        assert captured["cwd"] == qa_workspace
        assert "pytest" in captured["cmd"]


class TestCoverageAnalyzer:
    def test_invokes_pytest_with_cov_flags(self, qa_workspace: Path) -> None:
        captured: dict[str, object] = {}

        def fake_run(cmd, cwd, capture_output, text, timeout):  # noqa: ANN001
            captured["cmd"] = cmd
            return MagicMock(returncode=0, stdout="TOTAL ...\n", stderr="")

        with patch("ai_team.tools.qa_tools.subprocess.run", side_effect=fake_run):
            coverage_analyzer.run(source=".", test_target=".")

        cmd = captured["cmd"]
        assert any("--cov=" in str(a) for a in cmd)
        assert "--cov-branch" in cmd


class TestBugReporter:
    def test_normalizes_invalid_severity(self) -> None:
        out = bug_reporter.run(
            title="Flaky test",
            severity="URGENT",
            reproduction_steps="Run twice",
        )
        assert "Severity: medium" in out

    def test_includes_optional_fields(self) -> None:
        out = bug_reporter.run(
            title="Crash",
            severity="high",
            reproduction_steps="Click save",
            expected_behavior="Save",
            actual_behavior="500",
            file_path="app/views.py",
        )
        assert "high" in out
        assert "500" in out
        assert "views.py" in out


class TestLintRunner:
    def test_clean_run_returns_friendly_message(self, qa_workspace: Path) -> None:
        with patch("ai_team.tools.qa_tools.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            out = lint_runner.run(path=".")
        assert "No lint issues" in out


class TestGetQaTools:
    def test_returns_five_named_tools(self) -> None:
        tools = get_qa_tools()
        assert len(tools) == 5
        expected = [
            "Generate and persist a test file from path and content",
            "Run pytest in a directory or on specific paths",
            "Run coverage (pytest-cov) and return line/branch report",
            "Record a bug report with severity and reproduction steps",
            "Run linter (ruff) on a path and return issues",
        ]
        assert [t.name for t in tools] == expected
        assert all(callable(getattr(t, "run", None)) for t in tools)


def test_qa_min_coverage_default_is_eighty_percent() -> None:
    assert QA_MIN_COVERAGE_DEFAULT == 0.8
