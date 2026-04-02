"""Unit tests for ``CrewAIBackend`` with mocked ``run_ai_team``."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from ai_team.backends.crewai_backend.backend import CrewAIBackend
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile


@pytest.fixture
def profile() -> TeamProfile:
    return TeamProfile(name="full", agents=["manager"], phases=["intake", "planning"])


class TestCrewAIBackendRun:
    def test_run_success_maps_result(self, profile: TeamProfile) -> None:
        backend = CrewAIBackend()
        payload = {"phase": "complete", "ok": True}
        with patch(
            "ai_team.backends.crewai_backend.backend.run_ai_team",
            return_value=payload,
        ):
            r = backend.run("build a thing", profile, skip_estimate=True)
        assert isinstance(r, ProjectResult)
        assert r.success is True
        assert r.backend_name == "crewai"
        assert r.team_profile == "full"
        assert r.raw.get("team_profile") == "full"

    def test_run_failure_returns_error_result(self, profile: TeamProfile) -> None:
        backend = CrewAIBackend()
        with patch(
            "ai_team.backends.crewai_backend.backend.run_ai_team",
            side_effect=RuntimeError("boom"),
        ):
            r = backend.run("x", profile)
        assert r.success is False
        assert "boom" in (r.error or "")

    def test_stream_yields_start_and_finish(self, profile: TeamProfile) -> None:
        backend = CrewAIBackend()
        with patch.object(backend, "run", return_value=ProjectResult(
            backend_name="crewai",
            success=True,
            raw={},
            team_profile=profile.name,
        )):
            import asyncio

            async def collect() -> list[dict]:
                out: list[dict] = []
                async for ev in backend.stream("d", profile):
                    out.append(ev)
                return out

            events = asyncio.run(collect())
        assert events[0]["type"] == "run_started"
        assert events[-1]["type"] == "run_finished"
        assert events[-1]["success"] is True
