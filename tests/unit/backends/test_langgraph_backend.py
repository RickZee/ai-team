"""Unit tests for ``LangGraphBackend`` with mocked graph compile/invoke."""

from __future__ import annotations

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
