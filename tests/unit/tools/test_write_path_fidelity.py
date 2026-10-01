"""
Regression: a write must land where the agent asked, and the gate must collect it.

Found live on 2026-09-17 (`course/testing/runs/2026-09-17-stranger`, `logs/W1.S3.c1.txt`).
The smoke brief says "Output calc.py and test_calc.py only". Two write paths disagreed
about what that meant:

* ``_write_file_impl`` silently rewrote a root-level ``test_*.py`` to ``tests/test_*.py``
  (and, unreachably, also claimed to *refuse* root-level test files);
* the draft/commit path wrote ``test_calc.py`` exactly where the agent asked.

So the same suite ended up in both places. pytest hit an import-file mismatch on the
duplicate module name, the quality gate failed, and the graph burned three retries on
code that was correct the first time. The QA agent's closing message was "All 74 tests
pass (37 from root test_calc.py + 37 from tests/test_calc.py)".

The fix removes the relocation and gives the workspace its own pytest config so a
root-level test file is collected where it was written.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_team.config.settings import scoped_workspace_dir
from ai_team.tools.file_tools import _write_file_impl

TEST_SRC = "def test_ok() -> None:\n    assert True\n"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace" / "2026-09-17_run_01"
    ws.mkdir(parents=True)
    return ws


class TestWritePathIsHonoured:
    def test_root_level_test_file_is_not_relocated(self, workspace: Path) -> None:
        with scoped_workspace_dir(str(workspace)):
            _write_file_impl("test_calc.py", TEST_SRC)

        assert (workspace / "test_calc.py").read_text(encoding="utf-8") == TEST_SRC
        assert not (workspace / "tests").exists(), "write_file relocated the agent's file"

    def test_root_level_test_file_is_not_refused(self, workspace: Path) -> None:
        with scoped_workspace_dir(str(workspace)):
            assert _write_file_impl("test_calc.py", TEST_SRC) is True

    def test_explicit_tests_directory_is_honoured(self, workspace: Path) -> None:
        with scoped_workspace_dir(str(workspace)):
            _write_file_impl("tests/test_calc.py", TEST_SRC)

        assert (workspace / "tests" / "test_calc.py").exists()
        assert not (workspace / "test_calc.py").exists()

    def test_one_write_produces_exactly_one_file(self, workspace: Path) -> None:
        """The duplicate-suite condition that caused the import-file mismatch."""
        with scoped_workspace_dir(str(workspace)):
            _write_file_impl("test_calc.py", TEST_SRC)

        found = sorted(p.relative_to(workspace).as_posix() for p in workspace.rglob("test_*.py"))
        assert found == ["test_calc.py"]
