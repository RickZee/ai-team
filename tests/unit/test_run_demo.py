"""Unit tests for scripts/run_demo.py: --output and --monitor wiring."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

# Run demo script lives in scripts/; repo root is parent of scripts/
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_TODO = REPO_ROOT / "demos" / "02_todo_app"


def _load_run_demo_module():
    """Load scripts/run_demo.py in isolation (unique module name avoids sys.modules clashes)."""
    module_name = f"_run_demo_test_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(
        module_name, REPO_ROOT / "scripts" / "run_demo.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_demo_main(argv: list[str]):
    """Invoke run_demo.main() with mocks; never arm SIGALRM (Linux CI + pytest signals)."""
    with patch("ai_team.backends.crewai_backend.flows.main_flow.run_ai_team") as mock_run:
        mock_run.return_value = {"result": None, "state": {"current_phase": "complete"}}
        run_demo = _load_run_demo_module()
        with (
            patch.object(run_demo, "_install_timeout", return_value=False),
            patch.object(run_demo, "_finalize_run"),
            patch("sys.argv", argv),
            patch.dict("os.environ", {"AI_TEAM_ENV": "dev"}, clear=False),
        ):
            exit_code = run_demo.main()
        return exit_code, mock_run


class TestRunDemoOutputMode:
    """run_demo passes monitor only when --output tui or --monitor."""

    @pytest.fixture(autouse=True)
    def _ensure_demo_dir(self) -> None:
        if not DEMO_TODO.is_dir():
            pytest.skip(f"precondition: demo dir not found ({DEMO_TODO})")

    def test_run_demo_crewai_calls_run_ai_team_with_no_monitor(self) -> None:
        """With --output crewai, run_ai_team is called with monitor=None."""
        exit_code, mock_run = _run_demo_main(
            ["run_demo.py", "demos/02_todo_app", "--output", "crewai"],
        )
        assert exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args[1]["monitor"] is None
        assert mock_run.call_args[1]["team_profile"] == "full"

    def test_run_demo_tui_calls_run_ai_team_with_monitor(self) -> None:
        """With --output tui, run_ai_team is called with a TeamMonitor."""
        exit_code, mock_run = _run_demo_main(
            ["run_demo.py", "demos/02_todo_app", "--output", "tui"],
        )
        assert exit_code == 0
        mock_run.assert_called_once()
        mon = mock_run.call_args[1]["monitor"]
        assert mon is not None
        from ai_team.monitor import TeamMonitor

        assert isinstance(mon, TeamMonitor)

    def test_run_demo_monitor_flag_calls_run_ai_team_with_monitor(self) -> None:
        """With --monitor (shortcut for tui), run_ai_team is called with a monitor."""
        exit_code, mock_run = _run_demo_main(
            ["run_demo.py", "demos/02_todo_app", "--monitor"],
        )
        assert exit_code == 0
        assert mock_run.call_args[1]["monitor"] is not None


class TestRunDemoLoadDescription:
    """``load_project_description`` reads project_description.txt or input.json."""

    def test_load_description_from_input_json(self) -> None:
        """Demo 02 has input.json; content includes Flask REST API."""
        from ai_team.config.demo_input import load_project_description

        demo_dir = REPO_ROOT / "demos" / "02_todo_app"
        if not demo_dir.is_dir():
            pytest.skip(f"precondition: demo dir not found ({demo_dir})")
        desc = load_project_description(demo_dir)
        assert "Flask" in desc
        assert "REST API" in desc

    def test_load_description_from_txt(self, tmp_path: Path) -> None:
        """project_description.txt takes precedence when present."""
        from ai_team.config.demo_input import load_project_description

        demo_dir = tmp_path / "demo"
        demo_dir.mkdir()
        (demo_dir / "project_description.txt").write_text(
            "Create a Flask REST API with health checks.",
            encoding="utf-8",
        )
        desc = load_project_description(demo_dir)
        assert "Flask" in desc
        assert "REST API" in desc


class TestTimeoutAndFinalize:
    """The watchdog must not be swallowable, and CLI runs must close their run record."""

    def test_timeout_error_escapes_except_exception(self) -> None:
        run_demo = _load_run_demo_module()
        assert not issubclass(run_demo.DemoTimeoutError, Exception)
        with pytest.raises(run_demo.DemoTimeoutError):
            try:
                raise run_demo.DemoTimeoutError("t")
            except Exception:  # the pattern subgraphs use; must not catch it
                pytest.fail("DemoTimeoutError was swallowed by except Exception")

    @pytest.fixture()
    def out_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        from ai_team.config.settings import reload_settings

        monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(tmp_path / "out"))
        monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(tmp_path / "ws"))
        reload_settings()
        yield tmp_path / "out"
        monkeypatch.delenv("PROJECT_OUTPUT_DIR")
        monkeypatch.delenv("PROJECT_WORKSPACE_DIR")
        reload_settings()

    @staticmethod
    def _run_json(root: Path, run_id: str, **fields: object) -> Path:
        import json

        d = root / "runs" / run_id
        d.mkdir(parents=True)
        path = d / "run.json"
        path.write_text(json.dumps({"project_id": run_id, **fields}), encoding="utf-8")
        return path

    def test_finalize_closes_only_this_invocations_open_record(self, out_root: Path) -> None:
        import json
        import os
        import time

        run_demo = _load_run_demo_module()
        old = self._run_json(out_root, "old", completed_at=None)
        os.utime(old, (time.time() - 3600, time.time() - 3600))
        done = self._run_json(out_root, "done", completed_at="2026-09-16T00:00:00+00:00")
        new = self._run_json(out_root, "new", completed_at=None)
        run_demo._RUN_CONTEXT.update(started=time.time() - 60, backend="langgraph")

        run_demo._finalize_run("timeout")

        new_data = json.loads(new.read_text(encoding="utf-8"))
        assert new_data["completed_at"]
        assert new_data["extra"]["final_status"] == "timeout"
        assert new_data["backend"] == "langgraph"
        assert json.loads(old.read_text(encoding="utf-8"))["completed_at"] is None
        assert json.loads(done.read_text(encoding="utf-8"))["completed_at"].startswith("2026-09-16")

    def test_main_returns_124_and_finalizes_on_timeout(self) -> None:
        run_demo = _load_run_demo_module()
        with (
            patch.object(run_demo, "_install_timeout", return_value=False),
            patch.object(run_demo, "_finalize_run") as fin,
            patch.object(run_demo, "_run_backend", side_effect=run_demo.DemoTimeoutError("t")),
            patch("sys.argv", ["run_demo.py", "demos/00_smoke_test", "--backend", "langgraph"]),
        ):
            assert run_demo.main() == 124
        fin.assert_called_once_with("timeout")
