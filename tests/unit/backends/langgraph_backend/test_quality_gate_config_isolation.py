"""
Regression: the workspace quality gate must not inherit the repo's pytest config.

Found live on 2026-09-17 (`course/testing/runs/2026-09-17-stranger`). The smoke brief
says "Output calc.py and test_calc.py only". The agent complied and wrote
``test_calc.py`` at the workspace root. The QA agent's own ``pytest <dir>`` collected
24 passing tests. The harness gate — ``pytest -q --rootdir=<workspace>`` with no path
argument — collected **0** items and returned exit 5, because ``--rootdir`` does not
stop config discovery: pytest walked up out of ``workspace/<run_id>/`` into the repo,
found ``[tool.pytest.ini_options] testpaths = ["tests"]``, and resolved it against the
overridden rootdir. Three retries were spent on correct code before the model guessed
that it had to move the file into ``tests/``.

These tests run the real gate against a workspace nested under a parent that carries a
repo-shaped ``pyproject.toml``, which is what makes them fail on the old code.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ai_team.backends.langgraph_backend.graphs import subgraph_runners as sr
from ai_team.config.settings import scoped_workspace_dir

# A stand-in for ai-team's own pyproject.toml: the per-run workspace lives inside the
# repo, so whatever the repo configures for pytest and ruff is what the workspace
# inherits unless the gate says otherwise.
REPO_SHAPED_PYPROJECT = """\
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
ignore = ["E501"]
"""

CALC = """\
def add(a: int, b: int) -> int:
    \"\"\"Return the sum of a and b.\"\"\"
    return a + b
"""

ROOT_LEVEL_TEST = """\
from calc import add


def test_add() -> None:
    assert add(2, 3) == 5
"""


@pytest.fixture
def nested_workspace(tmp_path: Path) -> Path:
    """A run workspace sitting inside a repo that configures pytest, as in production."""
    (tmp_path / "pyproject.toml").write_text(REPO_SHAPED_PYPROJECT, encoding="utf-8")
    ws = tmp_path / "workspace" / "2026-09-17_run_01"
    ws.mkdir(parents=True)
    return ws


class TestGateCollectsRootLevelTests:
    def test_root_level_test_file_passes_the_gate(self, nested_workspace: Path) -> None:
        (nested_workspace / "calc.py").write_text(CALC, encoding="utf-8")
        (nested_workspace / "test_calc.py").write_text(ROOT_LEVEL_TEST, encoding="utf-8")

        with scoped_workspace_dir(str(nested_workspace)):
            result = sr._run_real_quality_gate()

        # Old code: returncode 5, no_tests_collected, passed False -> a wasted retry.
        assert result["tests"]["returncode"] == 0, result["tests"]["output"]
        assert "no_tests_collected" not in result
        assert result["passed"] is True

    def test_tests_subdirectory_still_passes_the_gate(self, nested_workspace: Path) -> None:
        (nested_workspace / "calc.py").write_text(CALC, encoding="utf-8")
        (nested_workspace / "tests").mkdir()
        (nested_workspace / "tests" / "test_calc.py").write_text(ROOT_LEVEL_TEST, encoding="utf-8")

        with scoped_workspace_dir(str(nested_workspace)):
            result = sr._run_real_quality_gate()

        assert result["tests"]["returncode"] == 0, result["tests"]["output"]
        assert result["passed"] is True

    def test_genuinely_missing_tests_still_report_exit_5(self, nested_workspace: Path) -> None:
        """The isolation must not paper over the real "QA wrote no tests" signal."""
        (nested_workspace / "calc.py").write_text(CALC, encoding="utf-8")

        with scoped_workspace_dir(str(nested_workspace)):
            result = sr._run_real_quality_gate()

        assert result["tests"]["returncode"] == 5
        assert result.get("no_tests_collected") is True
        assert result["passed"] is False

    def test_failing_tests_are_still_a_failure(self, nested_workspace: Path) -> None:
        (nested_workspace / "calc.py").write_text(CALC, encoding="utf-8")
        (nested_workspace / "test_calc.py").write_text(
            "from calc import add\n\n\ndef test_add() -> None:\n    assert add(2, 3) == 6\n",
            encoding="utf-8",
        )

        with scoped_workspace_dir(str(nested_workspace)):
            result = sr._run_real_quality_gate()

        assert result["tests"]["returncode"] == 1
        assert "no_tests_collected" not in result
        assert result["passed"] is False


class TestGateLintsOnWorkspaceTerms:
    """The gate must not fail generated code on this repo's house style.

    On 2026-09-17 a generated ``calc.py`` using ``Union[int, float]`` failed
    ``ruff check .`` on UP007 — inherited from ai-team's own ``select`` list. The brief
    never asked for ``X | Y``, and the agent could not watch itself fix it: its writes
    were pending drafts while its ruff tool read the committed file. It retried the same
    edit six times, then the graph retried the phase.
    """

    def test_union_annotations_do_not_fail_the_gate(self, nested_workspace: Path) -> None:
        (nested_workspace / "calc.py").write_text(
            "from typing import Union\n"
            "\n"
            "Numeric = Union[int, float]\n"
            "\n"
            "\n"
            "def add(a: Numeric, b: Numeric) -> Numeric:\n"
            '    """Return the sum of a and b."""\n'
            "    return a + b\n",
            encoding="utf-8",
        )
        (nested_workspace / "test_calc.py").write_text(ROOT_LEVEL_TEST, encoding="utf-8")

        with scoped_workspace_dir(str(nested_workspace)):
            result = sr._run_real_quality_gate()

        assert result["lint"]["returncode"] == 0, result["lint"]["output"]
        assert result["passed"] is True

    def test_a_real_error_still_fails_the_gate(self, nested_workspace: Path) -> None:
        (nested_workspace / "calc.py").write_text(
            "def add(a, b):\n    return undefined_name + a + b\n", encoding="utf-8"
        )
        (nested_workspace / "test_calc.py").write_text(
            "def test_ok() -> None:\n    assert True\n", encoding="utf-8"
        )

        with scoped_workspace_dir(str(nested_workspace)):
            result = sr._run_real_quality_gate()

        assert result["lint"]["returncode"] != 0
        assert result["passed"] is False


class TestGateWritesItsOwnConfig:
    def test_workspace_gets_a_pytest_ini_and_keeps_an_existing_one(
        self, nested_workspace: Path
    ) -> None:
        ini = sr._ensure_workspace_pytest_ini(nested_workspace)
        assert ini.exists()
        assert "testpaths = ." in ini.read_text(encoding="utf-8")

        ini.write_text("[pytest]\n# hand-edited\n", encoding="utf-8")
        sr._ensure_workspace_pytest_ini(nested_workspace)
        assert "hand-edited" in ini.read_text(encoding="utf-8")

    def test_workspace_gets_its_own_ruff_config(self, nested_workspace: Path) -> None:
        cfg = sr._ensure_workspace_ruff_config(nested_workspace)
        assert cfg.exists()
        assert "line-length" in cfg.read_text(encoding="utf-8")

    def test_gate_leaves_no_pytest_cache_in_the_workspace(self, nested_workspace: Path) -> None:
        (nested_workspace / "calc.py").write_text(CALC, encoding="utf-8")
        (nested_workspace / "test_calc.py").write_text(ROOT_LEVEL_TEST, encoding="utf-8")

        with scoped_workspace_dir(str(nested_workspace)):
            sr._run_real_quality_gate()

        assert not (nested_workspace / ".pytest_cache").exists()
