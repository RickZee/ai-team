"""Web dashboard API E2E — demo simulation and mocked runs (zero LLM cost)."""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.web_e2e


class TestWebApiHealthAndCatalog:
    def test_health(self, web_http_client: httpx.Client) -> None:
        r = web_http_client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_profiles_include_full(self, web_http_client: httpx.Client) -> None:
        r = web_http_client.get("/api/profiles")
        assert r.status_code == 200
        profiles = r.json()
        assert "full" in profiles
        assert "agents" in profiles["full"]
        assert "phases" in profiles["full"]

    def test_backends_include_three_orchestrators(self, web_http_client: httpx.Client) -> None:
        r = web_http_client.get("/api/backends")
        assert r.status_code == 200
        names = {b["name"] for b in r.json()["backends"]}
        assert names >= {"crewai", "langgraph", "claude-agent-sdk"}

    def test_estimate_simple(self, web_http_client: httpx.Client) -> None:
        r = web_http_client.post("/api/estimate", json={"complexity": "simple"})
        assert r.status_code == 200
        body = r.json()
        assert body["complexity"] == "simple"
        assert body["total_usd"] >= 0
        assert isinstance(body["rows"], list)
        assert len(body["rows"]) >= 1


class TestWebApiDemoFlow:
    """Demo uses ``_run_demo_async`` — no OpenRouter/Anthropic calls."""

    def test_demo_run_reaches_complete_via_rest(self, web_http_client: httpx.Client) -> None:
        start = web_http_client.post("/api/demo")
        assert start.status_code == 200
        run_id = start.json()["run_id"]

        deadline = time.monotonic() + 90.0
        last: dict[str, object] = {}
        while time.monotonic() < deadline:
            detail = web_http_client.get(f"/api/runs/{run_id}")
            assert detail.status_code == 200
            last = detail.json()
            if last.get("status") == "complete":
                break
            time.sleep(0.5)
        else:
            pytest.fail(f"Demo did not complete in time; last status={last.get('status')}")

        assert last["backend"] == "demo"
        monitor = last.get("monitor")
        assert monitor is not None
        assert monitor.get("phase") == "complete"
        assert monitor.get("metrics", {}).get("tasks_completed", 0) >= 0

    @pytest.mark.asyncio
    async def test_demo_monitor_websocket_stream(self, web_server_url: str) -> None:
        async with httpx.AsyncClient(base_url=web_server_url, timeout=90.0) as client:
            start = await client.post("/api/demo")
            assert start.status_code == 200
            run_id = start.json()["run_id"]

        import websockets

        phases_seen: list[str] = []
        ws_url = web_server_url.replace("http://", "ws://") + f"/ws/monitor/{run_id}"
        deadline = time.monotonic() + 90.0
        async with websockets.connect(ws_url) as ws:
            while time.monotonic() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                msg = json.loads(raw)
                if msg.get("type") == "monitor_update":
                    phase = msg.get("data", {}).get("phase")
                    if phase and (not phases_seen or phases_seen[-1] != phase):
                        phases_seen.append(phase)
                if msg.get("type") == "complete":
                    break
                if msg.get("type") == "error":
                    pytest.fail(msg.get("message", "monitor error"))

        assert "planning" in phases_seen or "development" in phases_seen
        assert phases_seen[-1] == "complete"

    def test_demo_appears_in_run_list(self, web_http_client: httpx.Client) -> None:
        start = web_http_client.post("/api/demo")
        run_id = start.json()["run_id"]
        runs = web_http_client.get("/api/runs").json()["runs"]
        assert any(r["run_id"] == run_id for r in runs)


class TestWebApiMockedRunWebSocket:
    """WebSocket run path with mocked backend execution (no LLM)."""

    def test_ws_run_mocked_completes(self, web_client: TestClient) -> None:
        async def _fake_execute(ws, run_id: str, req) -> None:  # noqa: ANN001
            from ai_team.monitor import TeamMonitor

            monitor = TeamMonitor(project_name="e2e-mock")
            monitor.on_phase_change("planning")
            monitor.on_log("manager", "mock step", "info")
            await ws.send_json(
                {
                    "type": "monitor_update",
                    "data": {
                        "phase": "planning",
                        "elapsed": "0s",
                        "agents": {},
                        "metrics": {
                            "tasks_completed": 1,
                            "tasks_failed": 0,
                            "retries": 0,
                            "files_generated": 0,
                            "guardrails_passed": 0,
                            "guardrails_failed": 0,
                            "guardrails_warned": 0,
                            "tests_passed": 0,
                            "tests_failed": 0,
                        },
                        "log": [],
                        "guardrail_events": [],
                    },
                }
            )
            await ws.send_json({"type": "complete", "data": {}})

        with (
            patch("ai_team.ui.web.server._execute_run", side_effect=_fake_execute),
            web_client.websocket_connect("/ws/run") as ws,
        ):
            ws.send_json(
                {
                    "backend": "crewai",
                    "profile": "prototype",
                    "description": "E2E mock run",
                    "complexity": "simple",
                }
            )
            started = ws.receive_json()
            assert started["type"] == "run_started"
            assert "run_id" in started

            saw_monitor = False
            saw_complete = False
            while not saw_complete:
                msg = ws.receive_json()
                if msg["type"] == "monitor_update":
                    saw_monitor = True
                if msg["type"] == "complete":
                    saw_complete = True
            assert saw_monitor

    def test_ws_run_unknown_monitor_returns_error(self, web_client: TestClient) -> None:
        with web_client.websocket_connect("/ws/monitor/nonexistent-run-id") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"


class TestWebApiRunNotFound:
    def test_get_missing_run_returns_404(self, web_http_client: httpx.Client) -> None:
        r = web_http_client.get("/api/runs/does-not-exist-xyz")
        assert r.status_code == 404


class TestWebApiRunsCatalog:
    def test_list_runs_includes_assignment_and_started_at(
        self, web_http_client: httpx.Client
    ) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run(
            "e2e-list",
            "langgraph",
            "full",
            "E2E assignment: build a widget",
        )
        runs = web_http_client.get("/api/runs").json()["runs"]
        row = next(r for r in runs if r["run_id"] == "e2e-list")
        assert row["description"] == "E2E assignment: build a widget"
        assert row["started_at"]

    def test_get_run_returns_full_assignment(self, web_http_client: httpx.Client) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run(
            "e2e-get",
            "crewai",
            "full",
            "Full assignment text for detail view",
        )
        r = web_http_client.get("/api/runs/e2e-get")
        assert r.status_code == 200
        assert r.json()["description"] == "Full assignment text for detail view"


class TestWebApiResume:
    def test_resume_rejects_non_awaiting_run(self, web_http_client: httpx.Client) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("e2e-r1", "langgraph", "full", "E2E resume test")
        web_server.state.runs["e2e-r1"]["status"] = "complete"
        r = web_http_client.post("/api/runs/e2e-r1/resume", json={"feedback": "approved"})
        assert r.status_code == 400

    def test_resume_rejects_non_langgraph_backend(self, web_http_client: httpx.Client) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("e2e-r2", "crewai", "full", "E2E crewai")
        web_server.state.set_awaiting_human("e2e-r2", {"phase": "awaiting_human"})
        r = web_http_client.post("/api/runs/e2e-r2/resume", json={"feedback": "ok"})
        assert r.status_code == 400


class TestWebApiMockedHitlWebSocket:
    def test_ws_run_sends_hitl_required_without_complete(self, web_client: TestClient) -> None:
        async def _hitl_execute(ws, run_id: str, req) -> None:  # noqa: ANN001
            from ai_team.ui.web import server as web_server

            web_server.state.set_awaiting_human(run_id, {"phase": "awaiting_human"})
            await ws.send_json(
                {
                    "type": "hitl_required",
                    "data": {"phase": "awaiting_human", "run_id": run_id},
                }
            )

        with (
            patch("ai_team.ui.web.server._execute_run", side_effect=_hitl_execute),
            web_client.websocket_connect("/ws/run") as ws,
        ):
            ws.send_json(
                {
                    "backend": "langgraph",
                    "profile": "full",
                    "description": "HITL mock",
                    "complexity": "simple",
                }
            )
            assert ws.receive_json()["type"] == "run_started"
            msg = ws.receive_json()
            assert msg["type"] == "hitl_required"
            assert msg["data"]["phase"] == "awaiting_human"
