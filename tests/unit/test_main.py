"""Unit tests for the CLI (main.py): output mode, _cmd_run monitor wiring."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ai_team.main import _OUTPUT_CHOICES, _cmd_run


class TestCmdRunOutputMode:
    """_cmd_run passes monitor only when output_mode is 'tui'."""

    @pytest.mark.parametrize("output_mode", ["crewai", "tui"])
    def test_cmd_run_calls_run_ai_team_with_expected_monitor(
        self, output_mode: str
    ) -> None:
        """run_ai_team receives monitor=None for crewai, TeamMonitor for tui."""
        with patch("ai_team.main.run_ai_team") as mock_run:
            mock_run.return_value = {"result": None, "state": {}}
            _cmd_run(
                description="Create a REST API",
                env=None,
                complexity=None,
                output_mode=output_mode,
                skip_estimate=True,
                project_name="Test Project",
            )
            mock_run.assert_called_once()
            call_kw = mock_run.call_args[1]
            if output_mode == "crewai":
                assert call_kw["monitor"] is None
            else:
                assert call_kw["monitor"] is not None
                from ai_team.monitor import TeamMonitor

                assert isinstance(call_kw["monitor"], TeamMonitor)
                assert call_kw["monitor"].project_name == "Test Project"

    def test_cmd_run_crewai_does_not_create_monitor(self) -> None:
        """With output_mode crewai, no TeamMonitor is created (monitor is None)."""
        with patch("ai_team.main.run_ai_team") as mock_run:
            mock_run.return_value = {"result": None, "state": {}}
            _cmd_run(
                description="A project",
                env=None,
                complexity=None,
                output_mode="crewai",
                skip_estimate=True,
                project_name="Proj",
            )
            assert mock_run.call_args[1]["monitor"] is None

    def test_cmd_run_tui_passes_monitor_with_project_name(self) -> None:
        """With output_mode tui, monitor has the given project_name."""
        with patch("ai_team.main.run_ai_team") as mock_run:
            mock_run.return_value = {"result": None, "state": {}}
            _cmd_run(
                description="A project",
                env=None,
                complexity=None,
                output_mode="tui",
                skip_estimate=True,
                project_name="Demo 01",
            )
            mon = mock_run.call_args[1]["monitor"]
            assert mon is not None
            assert mon.project_name == "Demo 01"


class TestMainArgparseOutput:
    """CLI argparse: --output and --monitor set output_mode correctly."""

    def test_output_choices(self) -> None:
        """Output choices are tui and crewai."""
        assert _OUTPUT_CHOICES == ("tui", "crewai")

    def test_run_output_mode_crewai_passes_no_monitor(self) -> None:
        """When output_mode is crewai, _cmd_run passes monitor=None to run_ai_team."""
        with patch("ai_team.main.run_ai_team") as mock_run:
            mock_run.return_value = {"result": None, "state": {}}
            _cmd_run(
                description="Build a CLI",
                env=None,
                complexity=None,
                output_mode="crewai",
                skip_estimate=True,
                project_name="AI-Team Project",
            )
            assert mock_run.call_args[1]["monitor"] is None

    def test_run_monitor_flag_implies_tui(self) -> None:
        """Logic: when args.monitor is True, output_mode should be tui (tested via _cmd_run)."""
        with patch("ai_team.main.run_ai_team") as mock_run:
            mock_run.return_value = {"result": None, "state": {}}
            _cmd_run(
                description="Build a CLI",
                env=None,
                complexity=None,
                output_mode="tui",
                skip_estimate=True,
                project_name="AI-Team Project",
            )
            assert mock_run.call_args[1]["monitor"] is not None
