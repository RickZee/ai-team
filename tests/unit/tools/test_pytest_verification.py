"""Tests for run_pytest verification and anti-hallucination helpers."""

from __future__ import annotations

import pytest
from ai_team.tasks.testing_tasks import _make_test_execution_guardrail
from ai_team.tools import test_tools as tt


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    tt.clear_verified_pytest_run()
    yield
    tt.clear_verified_pytest_run()


class TestFabricatedOutputDetection:
    def test_detects_linux_platform_on_darwin(self) -> None:
        raw = "============================= test session starts ==============================\nplatform linux -- Python 3.8.10"
        assert tt.looks_like_fabricated_pytest_output(raw) is True

    def test_accepts_realistic_session_header(self) -> None:
        import platform
        import sys

        py = f"{sys.version_info.major}.{sys.version_info.minor}"
        plat = platform.system().lower()
        raw = (
            "============================= test session starts ==============================\n"
            f"platform {plat} -- Python {py}\ncollected 1 item\n\n1 passed in 0.01s"
        )
        assert tt.looks_like_fabricated_pytest_output(raw) is False


class TestAgentResultVerification:
    def test_rejects_when_run_pytest_not_called(self) -> None:
        data = {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "errors": 0,
            "raw_output": "1 passed",
            "success": True,
        }
        ok, msg = tt.agent_test_result_matches_verified(data)
        assert ok is False
        assert "run_pytest" in msg

    def test_accepts_matching_verified_run(self) -> None:
        verified = tt.TestRunResult(
            total=1,
            passed=1,
            failed=0,
            errors=0,
            raw_output="collected 1 item\n1 passed in 0.01s",
            success=True,
        )
        tt._register_verified_pytest_run(verified)
        data = {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "errors": 0,
            "raw_output": "1 passed in 0.01s",
            "success": True,
        }
        ok, msg = tt.agent_test_result_matches_verified(data)
        assert ok is True
        assert msg == "ok"

    def test_rejects_count_mismatch(self) -> None:
        verified = tt.TestRunResult(
            total=1,
            passed=1,
            failed=0,
            errors=0,
            raw_output="1 passed",
            success=True,
        )
        tt._register_verified_pytest_run(verified)
        data = {"total": 6, "passed": 6, "failed": 0, "errors": 0, "raw_output": "6 passed"}
        ok, msg = tt.agent_test_result_matches_verified(data)
        assert ok is False
        assert "total" in msg


class TestExecutionGuardrail:
    def test_guardrail_rejects_unverified_json(self) -> None:
        guardrail = _make_test_execution_guardrail(0.0)
        fake = (
            '{"total": 6, "passed": 6, "failed": 0, "errors": 0, '
            '"raw_output": "platform linux -- Python 3.8.10", "success": true}'
        )
        passed, msg = guardrail(fake)
        assert passed is False
        assert isinstance(msg, str)

    def test_guardrail_accepts_verified_json(self) -> None:
        verified = tt.TestRunResult(
            total=1,
            passed=1,
            failed=0,
            errors=0,
            raw_output="collected 1 item\n1 passed in 0.01s",
            success=True,
        )
        tt._register_verified_pytest_run(verified)
        guardrail = _make_test_execution_guardrail(0.0)
        payload = verified.model_dump_json()
        passed, _ = guardrail(payload)
        assert passed is True


class TestDiscoverWorkspace:
    def test_discovers_tests_only_under_workspace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        tests_dir = workspace / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_calc.py").write_text(
            "def test_add():\n    assert 1 + 2 == 3\n",
            encoding="utf-8",
        )
        # Repo-root-style noise outside workspace — must not be collected.
        (tmp_path / "evals").mkdir()
        (tmp_path / "evals" / "test_noise.py").write_text("def test_x(): pass\n", encoding="utf-8")

        monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(workspace))
        from ai_team.config.settings import reload_settings

        reload_settings()
        monkeypatch.chdir(tmp_path)

        def _fake_run(test_path: str, source_path: str, *, workspace: Path | None = None) -> tt.TestRunResult:
            return tt.TestRunResult(
                total=1,
                passed=1,
                failed=0,
                errors=0,
                success=True,
                raw_output=f"ran {test_path} ws={workspace}",
            )

        monkeypatch.setattr(tt, "run_pytest", _fake_run)
        result = tt.run_pytest_discover_workspace()

        assert result is not None
        assert result.success is True
        assert "tests" in result.raw_output
