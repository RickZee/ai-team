"""Unit tests for testing crew orchestration and test file persistence."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ai_team.crews import testing_crew as tc
from ai_team.models.development import CodeFile
from ai_team.tools import test_tools as tt


@pytest.fixture(autouse=True)
def _clear_pytest_registry() -> None:
    tt.clear_verified_pytest_run()
    yield
    tt.clear_verified_pytest_run()


class TestPersistDevTestFiles:
    def test_writes_root_level_test_to_tests_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(tmp_path))
        from ai_team.config.settings import reload_settings

        reload_settings()
        monkeypatch.chdir(tmp_path)

        files = [
            CodeFile(
                path="calc.py",
                content="def add(a, b):\n    return a + b\n",
                language="python",
                description="calc module",
            ),
            CodeFile(
                path="test_calc.py",
                content="from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
                language="python",
                description="calc tests",
            ),
        ]
        count = tc._persist_test_files_from_code_files(files)
        assert count == 1
        assert (tmp_path / "tests" / "test_calc.py").is_file()


class TestOrchestratedPytestSalvage:
    def test_kickoff_runs_pytest_when_crew_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(tmp_path))
        from ai_team.config.settings import reload_settings

        reload_settings()
        monkeypatch.chdir(tmp_path)
        (tmp_path / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_calc.py").write_text(
            "from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
            encoding="utf-8",
        )

        code_files = [
            CodeFile(
                path="calc.py",
                content="def add(a, b):\n    return a + b\n",
                language="python",
                description="calc module",
            ),
        ]
        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = ValueError("Invalid response from LLM call - None or empty.")

        with patch.object(tc, "create_testing_crew", return_value=mock_crew):
            output = tc.kickoff(code_files, verbose=False)

        assert output.test_run_result is not None
        assert output.test_run_result.success is True
        assert "passed" in output.test_run_result.raw_output.lower()
        assert tt.get_verified_pytest_run() is not None


class TestCreateTestingCrewTasks:
    def test_default_does_not_add_test_execution_task(self) -> None:
        fake_task = MagicMock()
        with patch.object(tc, "test_generation_task", return_value=fake_task):
            with patch.object(tc, "code_review_task", return_value=fake_task):
                with patch.object(tc, "test_execution_task") as mock_exec:
                    with patch.object(tc, "Crew") as mock_crew_cls:
                        mock_crew_cls.return_value = MagicMock()
                        with patch.object(tc, "create_qa_engineer", return_value=MagicMock()):
                            with patch.object(tc, "crew_memory_enabled", return_value=False):
                                tc.create_testing_crew(verbose=False, agent_test_execution=False)
        mock_exec.assert_not_called()
