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
