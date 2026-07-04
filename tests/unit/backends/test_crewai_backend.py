"""Unit tests for ``CrewAIBackend`` with mocked ``run_ai_team``."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from ai_team.backends.crewai_backend.backend import CrewAIBackend
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile


@pytest.fixture
def profile() -> TeamProfile:
    return TeamProfile(name="full", agents=["manager"], phases=["intake", "planning"])


def _stub_subprocess_success(
    description: str, profile_name: str, kwargs: dict[str, Any], result_path: str
) -> None:
    """Fast stand-in for ``_run_crewai_subprocess`` (module-level: must be
    picklable-by-reference for ``multiprocessing`` "spawn")."""
    Path(result_path).write_text(
        json.dumps({"success": True, "raw": {"project_id": "test-id"}, "error": None}),
        encoding="utf-8",
    )


def _stub_subprocess_hangs(
    description: str, profile_name: str, kwargs: dict[str, Any], result_path: str
) -> None:
    """Never returns — exercises the hard wall-clock kill path."""
    time.sleep(3600)


class TestCrewAIBackendRun:
    def test_run_success_maps_result(self, profile: TeamProfile) -> None:
        backend = CrewAIBackend()
        payload = {
            "state": {
                "project_id": "test-id",
                "current_phase": "complete",
                "generated_files": [],
                "phase_history": [],
                "retry_counts": {},
                "metadata": {},
            }
        }
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
        assert r.raw.get("project_id") == "test-id"

    def test_run_incomplete_phase_maps_failure(self, profile: TeamProfile) -> None:
        backend = CrewAIBackend()
        payload = {
            "state": {
                "project_id": "test-id",
                "current_phase": "testing",
            }
        }
        with patch(
            "ai_team.backends.crewai_backend.backend.run_ai_team",
            return_value=payload,
        ):
            r = backend.run("build a thing", profile, skip_estimate=True)
        assert r.success is False

    def test_console_formatter_disabled(self) -> None:
        from ai_team.backends.crewai_backend.backend import _disable_crewai_console

        pytest.importorskip("crewai")
        from crewai.events.event_listener import EventListener

        _disable_crewai_console()
        el = EventListener()
        assert el.formatter.verbose is False
        assert el.formatter._is_streaming is True

    def test_run_does_not_leak_stale_workspace_env(
        self, profile: TeamProfile, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stale PROJECT_WORKSPACE_DIR left by an earlier run in the same
        process (e.g. web server or multi-backend comparison) must not leak
        into a .run() call that omits workspace_dir — otherwise main_flow's
        fallback nests the new project_id under the old run's directory
        instead of workspace/<project_id>/ directly."""
        stale = "/tmp/leftover-run-from-unrelated-demo"
        monkeypatch.setenv("PROJECT_WORKSPACE_DIR", stale)

        seen: dict[str, str] = {}

        def _capture_workspace(*args: Any, **kwargs: Any) -> dict[str, Any]:
            from ai_team.config.settings import get_settings

            seen["workspace_dir"] = get_settings().project.workspace_dir
            return {"state": {"project_id": "test-id", "current_phase": "complete"}}

        with patch(
            "ai_team.backends.crewai_backend.backend.run_ai_team",
            side_effect=_capture_workspace,
        ):
            backend = CrewAIBackend()
            backend.run("build a thing", profile, skip_estimate=True)

        assert seen["workspace_dir"] != stale

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
        """Real subprocess (spawn), stub target — exercises actual pickling/IPC,
        not just the orchestration logic, since that's the point of this backend."""
        backend = CrewAIBackend()

        async def collect() -> list[dict]:
            out: list[dict] = []
            async for ev in backend.stream(
                "d", profile, _subprocess_target=_stub_subprocess_success
            ):
                out.append(ev)
            return out

        import asyncio

        events = asyncio.run(collect())
        assert events[0]["type"] == "run_started"
        assert events[-1]["type"] == "run_finished"
        assert events[-1]["success"] is True
        assert events[-1]["result"]["raw"]["project_id"] == "test-id"

    def test_stream_hard_kills_on_timeout(self, profile: TeamProfile) -> None:
        """A subprocess that never returns must be force-killed at the wall-clock
        deadline, not hang the caller — the whole point of subprocess isolation
        over the old thread-based approach (see docs/handoff-2026-07-01.md §9)."""
        backend = CrewAIBackend()

        async def collect() -> list[dict]:
            out: list[dict] = []
            async for ev in backend.stream(
                "d",
                profile,
                _subprocess_target=_stub_subprocess_hangs,
                _timeout_override_s=2,
            ):
                out.append(ev)
            return out

        import asyncio

        start = time.monotonic()
        events = asyncio.run(collect())
        elapsed = time.monotonic() - start

        assert elapsed < 30, "hard kill should bound wall-clock time close to the timeout"
        assert events[-1]["type"] == "run_finished"
        assert events[-1]["success"] is False
        assert "timeout" in (events[-1]["result"]["error"] or "").lower()
