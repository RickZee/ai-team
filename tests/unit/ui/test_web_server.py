"""REST API tests for ``ui.web.server``."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestWebServerProfilesAndBackends:
    def test_get_profiles(self, web_client: TestClient) -> None:
        r = web_client.get("/api/profiles")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert "full" in data or len(data) >= 1

    def test_get_backends(self, web_client: TestClient) -> None:
        r = web_client.get("/api/backends")
        assert r.status_code == 200
        names = {b["name"] for b in r.json()["backends"]}
        assert "crewai" in names
        assert "langgraph" in names


class TestWebServerEstimate:
    def test_post_estimate(self, web_client: TestClient) -> None:
        r = web_client.post("/api/estimate", json={"complexity": "simple"})
        assert r.status_code == 200
        body = r.json()
        assert "total_usd" in body
        assert body["complexity"] == "simple"


class TestWebServerDemo:
    def test_post_demo_returns_run_id(self, web_client: TestClient) -> None:
        r = web_client.post("/api/demo")
        assert r.status_code == 200
        assert "run_id" in r.json()


class TestWebServerHealth:
    def test_health(self, web_client: TestClient) -> None:
        r = web_client.get("/api/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


class TestWebServerRunRequestDefaults:
    """``RunRequest`` default backend is langgraph — document API contract."""

    def test_run_request_default_backend_documented(self, web_client: TestClient) -> None:
        from ai_team.ui.web.server import RunRequest

        r = RunRequest(description="x")
        assert r.backend == "langgraph"
