"""Unit tests for scripts/run_demo.py: --output and --monitor wiring."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Run demo script lives in scripts/; repo root is parent of scripts/
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_01 = REPO_ROOT / "demos" / "01_hello_world"


class TestRunDemoOutputMode:
    """run_demo passes monitor only when --output tui or --monitor."""

    @pytest.fixture(autouse=True)
    def _ensure_demo_dir(self) -> None:
        if not DEMO_01.is_dir():
            pytest.skip(f"Demo dir not found: {DEMO_01}")

    def test_run_demo_crewai_calls_run_ai_team_with_no_monitor(self) -> None:
        """With --output crewai, run_ai_team is called with monitor=None."""
        with patch("ai_team.flows.main_flow.run_ai_team") as mock_run:
            mock_run.return_value = {"result": None, "state": {"current_phase": "complete"}}
            with patch("sys.argv", ["run_demo.py", "demos/01_hello_world", "--output", "crewai"]):
                with patch.dict("os.environ", {"AI_TEAM_ENV": "dev"}, clear=False):
                    # Import and run main from the script (run from repo root in tests)
                    import importlib.util

                    spec = importlib.util.spec_from_file_location(
                        "run_demo", REPO_ROOT / "scripts" / "run_demo.py"
                    )
                    assert spec is not None and spec.loader is not None
                    run_demo = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(run_demo)
                    exit_code = run_demo.main()
            assert exit_code == 0
            mock_run.assert_called_once()
            assert mock_run.call_args[1]["monitor"] is None

    def test_run_demo_tui_calls_run_ai_team_with_monitor(self) -> None:
        """With --output tui, run_ai_team is called with a TeamMonitor."""
        with patch("ai_team.flows.main_flow.run_ai_team") as mock_run:
            mock_run.return_value = {"result": None, "state": {"current_phase": "complete"}}
            with patch("sys.argv", ["run_demo.py", "demos/01_hello_world", "--output", "tui"]):
                with patch.dict("os.environ", {"AI_TEAM_ENV": "dev"}, clear=False):
                    import importlib.util

                    spec = importlib.util.spec_from_file_location(
                        "run_demo", REPO_ROOT / "scripts" / "run_demo.py"
                    )
                    assert spec is not None and spec.loader is not None
                    run_demo = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(run_demo)
                    exit_code = run_demo.main()
            assert exit_code == 0
            mock_run.assert_called_once()
            mon = mock_run.call_args[1]["monitor"]
            assert mon is not None
            from ai_team.monitor import TeamMonitor

            assert isinstance(mon, TeamMonitor)

    def test_run_demo_monitor_flag_calls_run_ai_team_with_monitor(self) -> None:
        """With --monitor (shortcut for tui), run_ai_team is called with a monitor."""
        with patch("ai_team.flows.main_flow.run_ai_team") as mock_run:
            mock_run.return_value = {"result": None, "state": {"current_phase": "complete"}}
            with patch("sys.argv", ["run_demo.py", "demos/01_hello_world", "--monitor"]):
                with patch.dict("os.environ", {"AI_TEAM_ENV": "dev"}, clear=False):
                    import importlib.util

                    spec = importlib.util.spec_from_file_location(
                        "run_demo", REPO_ROOT / "scripts" / "run_demo.py"
                    )
                    assert spec is not None and spec.loader is not None
                    run_demo = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(run_demo)
                    exit_code = run_demo.main()
            assert exit_code == 0
            assert mock_run.call_args[1]["monitor"] is not None


class TestRunDemoLoadDescription:
    """_load_description prefers project_description.txt and falls back to input.json."""

    def test_load_description_from_txt(self) -> None:
        """Demo 01 has project_description.txt; content is used."""
        import importlib.util

        demo_dir = REPO_ROOT / "demos" / "01_hello_world"
        if not demo_dir.is_dir():
            pytest.skip(f"Demo dir not found: {demo_dir}")
        spec = importlib.util.spec_from_file_location(
            "run_demo", REPO_ROOT / "scripts" / "run_demo.py"
        )
        assert spec is not None and spec.loader is not None
        run_demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run_demo)
        desc = run_demo._load_description(demo_dir)
        assert "Flask" in desc
        assert "REST API" in desc
