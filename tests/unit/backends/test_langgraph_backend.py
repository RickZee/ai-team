"""Unit tests for ``LangGraphBackend`` with mocked graph compile/invoke."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_team.backends.langgraph_backend.backend import LangGraphBackend
from ai_team.core.team_profile import TeamProfile


@pytest.fixture
def profile() -> TeamProfile:
    return TeamProfile(name="full", agents=["manager"], phases=["intake", "planning"])


class TestLangGraphBackendRun:
    def test_run_success_when_phase_complete(self, profile: TeamProfile) -> None:
        backend = LangGraphBackend()
        graph = MagicMock()
        graph.invoke.return_value = {"current_phase": "complete", "messages": []}
        with (
            patch.object(backend, "_compile_for_run", return_value=graph),
            patch.dict("os.environ", {"AI_TEAM_LANGGRAPH_POSTGRES_URI": ""}, clear=False),
        ):
            r = backend.run("desc", profile, graph_mode="placeholder")
        assert r.success is True
        assert r.raw.get("thread_id")
        graph.invoke.assert_called_once()

    def test_run_returns_failure_on_exception(self, profile: TeamProfile) -> None:
        backend = LangGraphBackend()
        with (
            patch.object(backend, "_compile_for_run", side_effect=OSError("nope")),
            patch.dict("os.environ", {"AI_TEAM_LANGGRAPH_POSTGRES_URI": ""}, clear=False),
        ):
            r = backend.run("d", profile, graph_mode="placeholder")
        assert r.success is False
        assert r.error


class TestPlaceholderTelemetry:
    def test_placeholder_run_writes_phase_log(self, profile: TeamProfile, tmp_path: Path) -> None:
        backend = LangGraphBackend()
        result = backend.run(
            "Write a tiny Python module and one test",
            profile,
            graph_mode="placeholder",
            workspace_dir=str(tmp_path / "ws"),
        )
        assert result.success is True
        run_id = result.raw["thread_id"]
        from ai_team.config.settings import get_settings

        log = Path(get_settings().project.output_dir) / "runs" / run_id / "logs" / "phases.jsonl"
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        phases = {row["phase"] for row in rows if row["status"] == "phase_end"}
        assert "planning" in phases
        assert "complete" in phases
        assert all(row["writer"] == "harness" for row in rows)
