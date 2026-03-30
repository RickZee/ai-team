"""Unit tests for the CLI (main.py): output mode, _cmd_run monitor wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from ai_team.backends.langgraph_backend.backend import LangGraphBackend
from ai_team.core.result import ProjectResult
from ai_team.main import _OUTPUT_CHOICES, _cmd_run, _preprocess_argv_for_subcommand


class TestCmdRunOutputMode:
    """_cmd_run passes monitor only when output_mode is 'tui' and backend is crewai."""

    @pytest.mark.parametrize("output_mode", ["crewai", "tui"])
    def test_cmd_run_calls_backend_run_with_expected_monitor(
        self, output_mode: str
    ) -> None:
        """CrewAI backend receives monitor=None for crewai, TeamMonitor for tui."""
        pr = ProjectResult(
            backend_name="crewai",
            success=True,
            raw={"result": None, "state": {}},
            team_profile="full",
        )
        mock_backend = MagicMock()
        mock_backend.run.return_value = pr
        with patch("ai_team.main.get_backend", return_value=mock_backend):
            _cmd_run(
                description="Create a REST API",
                env=None,
                complexity=None,
                output_mode=output_mode,
                skip_estimate=True,
                project_name="Test Project",
                backend_name="crewai",
                team="full",
            )
        mock_backend.run.assert_called_once()
        call_kw = mock_backend.run.call_args[1]
        if output_mode == "crewai":
            assert call_kw["monitor"] is None
        else:
            assert call_kw["monitor"] is not None
            from ai_team.monitor import TeamMonitor

            assert isinstance(call_kw["monitor"], TeamMonitor)
            assert call_kw["monitor"].project_name == "Test Project"

    def test_cmd_run_crewai_does_not_create_monitor(self) -> None:
        """With output_mode crewai, no TeamMonitor is created (monitor is None)."""
        pr = ProjectResult(
            backend_name="crewai",
            success=True,
            raw={"result": None, "state": {}},
            team_profile="full",
        )
        mock_backend = MagicMock()
        mock_backend.run.return_value = pr
        with patch("ai_team.main.get_backend", return_value=mock_backend):
            _cmd_run(
                description="A project",
                env=None,
                complexity=None,
                output_mode="crewai",
                skip_estimate=True,
                project_name="Proj",
                backend_name="crewai",
                team="full",
            )
        assert mock_backend.run.call_args[1]["monitor"] is None

    def test_cmd_run_tui_passes_monitor_with_project_name(self) -> None:
        """With output_mode tui, monitor has the given project_name."""
        pr = ProjectResult(
            backend_name="crewai",
            success=True,
            raw={"result": None, "state": {}},
            team_profile="full",
        )
        mock_backend = MagicMock()
        mock_backend.run.return_value = pr
        with patch("ai_team.main.get_backend", return_value=mock_backend):
            _cmd_run(
                description="A project",
                env=None,
                complexity=None,
                output_mode="tui",
                skip_estimate=True,
                project_name="Demo 01",
                backend_name="crewai",
                team="full",
            )
        mon = mock_backend.run.call_args[1]["monitor"]
        assert mon is not None
        assert mon.project_name == "Demo 01"


class TestCmdRunLangGraph:
    """LangGraph: resume and stream paths use real backend type checks."""

    def test_langgraph_resume_calls_backend_resume(self) -> None:
        """``resume_thread`` set invokes ``LangGraphBackend.resume``."""
        pr = ProjectResult(
            backend_name="langgraph",
            success=True,
            raw={"state": {}, "thread_id": "tid-abc"},
            team_profile="full",
        )
        backend = LangGraphBackend()
        with (
            patch.object(backend, "resume", return_value=pr) as mock_resume,
            patch("ai_team.main.get_backend", return_value=backend),
        ):
            code = _cmd_run(
                description="",
                env=None,
                complexity=None,
                output_mode="crewai",
                skip_estimate=True,
                project_name="P",
                backend_name="langgraph",
                team="full",
                resume_thread="tid-abc",
                resume_input="approved",
            )
        assert code == 0
        mock_resume.assert_called_once()
        assert mock_resume.call_args[0][0] == "tid-abc"
        assert mock_resume.call_args[0][1] == "approved"

    def test_langgraph_stream_uses_iter_stream_events(self) -> None:
        """``stream`` + langgraph iterates ``iter_stream_events``."""
        events = [
            {"type": "run_started", "thread_id": "x"},
            {"type": "langgraph_done", "thread_id": "x", "state": {}},
        ]

        def fake_iter(
            _desc: str,
            _profile: object,
            **_: object,
        ) -> object:
            yield from events

        backend = LangGraphBackend()
        with (
            patch.object(
                backend,
                "iter_stream_events",
                side_effect=fake_iter,
            ) as mock_iter,
            patch("ai_team.main.get_backend", return_value=backend),
        ):
            code = _cmd_run(
                description="Build a thing",
                env=None,
                complexity=None,
                output_mode="crewai",
                skip_estimate=True,
                project_name="P",
                backend_name="langgraph",
                team="full",
                stream=True,
            )
        assert code == 0
        mock_iter.assert_called_once()


class TestPreprocessArgvForSubcommand:
    """Implicit ``run`` is inserted only when the first token is not a flag or subcommand."""

    def test_empty_unchanged(self) -> None:
        assert _preprocess_argv_for_subcommand([]) == []

    def test_run_and_subcommands_unchanged(self) -> None:
        assert _preprocess_argv_for_subcommand(["run", "x"]) == ["run", "x"]
        assert _preprocess_argv_for_subcommand(["estimate"]) == ["estimate"]
        assert _preprocess_argv_for_subcommand(["compare-costs"]) == ["compare-costs"]

    def test_flag_first_unchanged(self) -> None:
        assert _preprocess_argv_for_subcommand(["--backend", "langgraph", "run", "d"]) == [
            "--backend",
            "langgraph",
            "run",
            "d",
        ]

    def test_implicit_run_prepended(self) -> None:
        assert _preprocess_argv_for_subcommand(["Build a todo app"]) == [
            "run",
            "Build a todo app",
        ]


class TestMainArgparseOutput:
    """CLI argparse: --output and --monitor set output_mode correctly."""

    def test_output_choices(self) -> None:
        """Output choices are tui and crewai."""
        assert _OUTPUT_CHOICES == ("tui", "crewai")

    def test_run_output_mode_crewai_passes_no_monitor(self) -> None:
        """When output_mode is crewai, backend.run receives monitor=None."""
        pr = ProjectResult(
            backend_name="crewai",
            success=True,
            raw={"result": None, "state": {}},
            team_profile="full",
        )
        mock_backend = MagicMock()
        mock_backend.run.return_value = pr
        with patch("ai_team.main.get_backend", return_value=mock_backend):
            _cmd_run(
                description="Build a CLI",
                env=None,
                complexity=None,
                output_mode="crewai",
                skip_estimate=True,
                project_name="AI-Team Project",
                backend_name="crewai",
                team="full",
            )
        assert mock_backend.run.call_args[1]["monitor"] is None

    def test_run_monitor_flag_implies_tui(self) -> None:
        """Logic: when output_mode is tui, backend.run receives a monitor."""
        pr = ProjectResult(
            backend_name="crewai",
            success=True,
            raw={"result": None, "state": {}},
            team_profile="full",
        )
        mock_backend = MagicMock()
        mock_backend.run.return_value = pr
        with patch("ai_team.main.get_backend", return_value=mock_backend):
            _cmd_run(
                description="Build a CLI",
                env=None,
                complexity=None,
                output_mode="tui",
                skip_estimate=True,
                project_name="AI-Team Project",
                backend_name="crewai",
                team="full",
            )
        assert mock_backend.run.call_args[1]["monitor"] is not None
