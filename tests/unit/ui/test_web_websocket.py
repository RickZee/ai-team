"""WebSocket tests for ``ui.web.server`` (mocked execution)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from fastapi.testclient import TestClient


class TestWebSocketRun:
    def test_ws_run_accepts_and_starts_run(self, web_client: TestClient) -> None:
        async def _noop_execute(ws, run_id: str, req) -> None:  # noqa: ANN001
            await ws.send_json({"type": "complete", "data": {}})

        with (
            patch("ai_team.ui.web.server._execute_run", side_effect=_noop_execute) as _,
            web_client.websocket_connect("/ws/run") as ws,
        ):
            ws.send_json(
                {
                    "backend": "crewai",
                    "profile": "full",
                    "description": "unit test",
                    "complexity": "simple",
                }
            )
            first = ws.receive_json()
            assert first["type"] == "run_started"
            assert "run_id" in first
            second = ws.receive_json()
            assert second["type"] == "complete"

    def test_safe_send_swallows_dead_client(self) -> None:
        """A closed run socket must not abort the run via a send failure.

        ``_execute_run`` streams over the /ws/run socket; once the client
        navigates away that socket is dead. ``_safe_send`` must swallow the
        failure so a dead client never propagates an exception into the run.
        """
        from ai_team.ui.web import server as web_server

        class _DeadWS:
            async def send_json(self, _payload: dict) -> None:
                raise RuntimeError("client disconnected")

        # Must not raise.
        asyncio.run(web_server._safe_send(_DeadWS(), {"type": "event", "data": {}}))

    def test_client_disconnect_does_not_cancel_run(self, web_client: TestClient) -> None:
        """Disconnecting the /ws/run client must not cancel the backend run.

        Navigating Run tab -> Dashboard closes the /ws/run socket. The run is
        detached and observed via /ws/monitor, so ``ws_run`` must not request
        cancellation on disconnect (regression for runs that died seconds after
        launch when the user switched tabs). Only an explicit /api cancel sets
        the cancel flag.
        """
        from ai_team.ui.web import server as web_server

        started = "ai_team.ui.web.server._execute_run"

        async def _noop_execute(ws, run_id: str, req) -> None:  # noqa: ANN001
            # Resolve immediately; the point of the test is the cancel flag,
            # not the run lifetime (portal teardown kills loop tasks in tests).
            return None

        with patch(started, side_effect=_noop_execute):
            with web_client.websocket_connect("/ws/run") as ws:
                ws.send_json(
                    {
                        "backend": "crewai",
                        "profile": "full",
                        "description": "disconnect test",
                        "complexity": "simple",
                    }
                )
                first = ws.receive_json()
                assert first["type"] == "run_started"
                run_id = first["run_id"]
            # Socket closed by leaving the context. Disconnect alone must not
            # have flagged the run for cancellation.
            assert web_server.state.is_cancel_requested(run_id) is False

        web_server.state.runs.pop(run_id, None)
        web_server.state.tasks.pop(run_id, None)
        web_server.state.cancel_flags.pop(run_id, None)

    def test_ws_monitor_unknown_run(self, web_client: TestClient) -> None:
        with web_client.websocket_connect("/ws/monitor/does-not-exist-xyz") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_ws_monitor_emits_hitl_required_when_awaiting_human(
        self, web_client: TestClient
    ) -> None:
        from ai_team.monitor import TeamMonitor
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("hitl-ws", "langgraph", "full", "Needs review")
        web_server.state.monitors["hitl-ws"] = TeamMonitor(project_name="Needs review")
        web_server.state.set_awaiting_human("hitl-ws", {"phase": "awaiting_human"})

        with web_client.websocket_connect("/ws/monitor/hitl-ws") as ws:
            first = ws.receive_json()
            assert first["type"] == "monitor_update"
            second = ws.receive_json()
            assert second["type"] == "hitl_required"
            assert second["data"]["phase"] == "awaiting_human"


class TestCrewAIMonitorBackfill:
    """CrewAI is subprocess-isolated (no live TeamMonitor); the Compare column
    used to show 0 tasks/0 files for the whole run because the monitor was
    never touched. ``_apply_crewai_result_to_monitor`` backfills a final
    snapshot from the subprocess result payload at run_finished."""

    def test_backfills_totals_on_success(self) -> None:
        from ai_team.monitor import Phase, TeamMonitor
        from ai_team.ui.web.server import _apply_crewai_result_to_monitor

        monitor = TeamMonitor(project_name="crewai backfill test")
        raw = {
            "state": {
                "generated_files": [{"path": "calc.py"}, {"path": "test_calc.py"}],
                "test_results": {"passed": 28, "failed": 0},
                "phase_history": [{"phase": "planning"}, {"phase": "development"}],
            }
        }

        _apply_crewai_result_to_monitor(monitor, raw, success=True)

        assert monitor.current_phase == Phase.COMPLETE
        assert monitor.metrics.files_generated == 2
        assert monitor.metrics.tasks_completed == 2
        assert monitor.metrics.tests_passed == 28
        assert monitor.metrics.tests_failed == 0

    def test_marks_error_phase_and_tolerates_missing_state(self) -> None:
        from ai_team.monitor import Phase, TeamMonitor
        from ai_team.ui.web.server import _apply_crewai_result_to_monitor

        monitor = TeamMonitor(project_name="crewai backfill error test")

        _apply_crewai_result_to_monitor(monitor, raw={}, success=False)

        assert monitor.current_phase == Phase.ERROR
        assert monitor.metrics.files_generated == 0
        assert monitor.metrics.tasks_completed == 0


class TestFinishRunFinalizesBundle:
    """finish_run must stamp the on-disk bundle (completed_at, final status,
    spend) — before this, run.json kept completed_at: null and costs.jsonl
    stayed empty for every backend (2026-07-03 comparison finding #5)."""

    def test_finish_run_writes_bundle_finalization(self, tmp_path, monkeypatch) -> None:
        import json as _json

        from ai_team.config.settings import reload_settings
        from ai_team.ui.web.server import RunState

        out_root = tmp_path / "out"
        monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out_root))
        monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(tmp_path / "ws"))
        reload_settings()

        st = RunState()
        st.create_run("run-1", backend="langgraph", profile="smoke", description="x")
        st.runs["run-1"]["spend"] = {"spent_usd": 0.05, "total_tokens": 42}
        st.finish_run("run-1", success=True)

        data = _json.loads(
            (out_root / "runs" / "run-1" / "run.json").read_text(encoding="utf-8")
        )
        assert data["completed_at"] is not None
        assert data["extra"]["final_status"] == "complete"
        costs = (out_root / "runs" / "run-1" / "logs" / "costs.jsonl").read_text(
            encoding="utf-8"
        )
        assert '"spent_usd": 0.05' in costs

    def test_hitl_approved_run_gets_distinct_final_status(
        self, tmp_path, monkeypatch
    ) -> None:
        """Complete-by-operator-approval must be distinguishable from
        complete-by-passing (finding #2 of the live rerun)."""
        import json as _json

        from ai_team.config.settings import reload_settings
        from ai_team.ui.web.server import RunState

        out_root = tmp_path / "out"
        monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out_root))
        monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(tmp_path / "ws"))
        reload_settings()

        st = RunState()
        st.create_run("run-2", backend="langgraph", profile="smoke", description="x")
        st.runs["run-2"]["approved_via_hitl"] = True
        st.finish_run("run-2", success=True)

        assert st.runs["run-2"]["status"] == "complete"
        data = _json.loads(
            (out_root / "runs" / "run-2" / "run.json").read_text(encoding="utf-8")
        )
        assert data["extra"]["final_status"] == "complete_approved"

    def test_finish_run_survives_broken_output_dir(self, tmp_path, monkeypatch) -> None:
        """Adversarial: bundle failure must never mask the run outcome."""
        from ai_team.config.settings import reload_settings
        from ai_team.ui.web.server import RunState

        monkeypatch.setenv("PROJECT_OUTPUT_DIR", "/dev/null/nope")
        monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(tmp_path / "ws"))
        reload_settings()

        st = RunState()
        st.create_run("run-3", backend="crewai", profile="smoke", description="x")
        st.finish_run("run-3", success=False, error="boom")

        assert st.runs["run-3"]["status"] == "error"
        assert st.runs["run-3"]["error"] == "boom"
