"""WebSocket tests for ``ui.web.server`` (mocked execution)."""

from __future__ import annotations

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

    def test_ws_monitor_unknown_run(self, web_client: TestClient) -> None:
        with web_client.websocket_connect("/ws/monitor/does-not-exist-xyz") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
