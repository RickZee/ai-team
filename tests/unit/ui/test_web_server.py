"""REST API tests for ``ui.web.server``."""

from __future__ import annotations

import pytest
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


class TestWebServerArtifacts:
    def test_registry_runs(self, web_client: TestClient) -> None:
        r = web_client.get("/api/registry/runs")
        assert r.status_code == 200
        assert "runs" in r.json()

    def test_project_tree_and_file(
        self,
        web_client: TestClient,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ws = tmp_path / "workspace"
        out = tmp_path / "output"
        ws.mkdir()
        out.mkdir()
        monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(ws))
        monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out))
        from ai_team.config.settings import reload_settings

        reload_settings()

        pid = "web-artifact-test"
        proj = ws / pid / "src"
        proj.mkdir(parents=True)
        (proj / "hello.py").write_text("x = 1\n", encoding="utf-8")

        tr = web_client.get(f"/api/projects/{pid}/tree", params={"root": "workspace"})
        assert tr.status_code == 200
        assert tr.json()["tree"]

        fr = web_client.get(
            f"/api/projects/{pid}/file",
            params={"path": "src/hello.py", "root": "workspace"},
        )
        assert fr.status_code == 200
        assert "x = 1" in fr.json()["content"]

    def test_project_tests_architecture_empty(
        self, web_client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws = tmp_path / "workspace"
        out = tmp_path / "output"
        ws.mkdir()
        out.mkdir()
        monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(ws))
        monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out))
        from ai_team.config.settings import reload_settings

        reload_settings()

        pid = "empty-proj"
        (ws / pid).mkdir()

        assert web_client.get(f"/api/projects/{pid}/tests").status_code == 200
        assert web_client.get(f"/api/projects/{pid}/architecture").status_code == 200

    def test_download_zip(
        self, web_client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws = tmp_path / "workspace"
        out = tmp_path / "output"
        ws.mkdir()
        out.mkdir()
        monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(ws))
        monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out))
        from ai_team.config.settings import reload_settings

        reload_settings()

        pid = "zip-proj"
        (ws / pid).mkdir()
        (ws / pid / "a.txt").write_text("data", encoding="utf-8")

        r = web_client.get(f"/api/projects/{pid}/download.zip")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        assert r.content[:2] == b"PK"


class TestWebServerRuns:
    def test_create_run_includes_metadata_fields(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        entry = web_server.state.create_run(
            "meta-1",
            "langgraph",
            "full",
            "Build a task API",
        )
        assert entry["thread_id"] == "meta-1"
        assert entry["description"] == "Build a task API"
        assert entry["started_at"]
        assert entry["hitl_payload"] is None

    def test_list_runs_returns_description_and_started_at(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("list-1", "demo", "full", "Demo assignment text")
        r = web_client.get("/api/runs")
        assert r.status_code == 200
        run = next(x for x in r.json()["runs"] if x["run_id"] == "list-1")
        assert run["description"] == "Demo assignment text"
        assert run["started_at"]

    def test_get_run_includes_monitor_and_description(self, web_client: TestClient) -> None:
        from ai_team.monitor import TeamMonitor
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("detail-1", "crewai", "full", "Detail assignment")
        web_server.state.monitors["detail-1"] = TeamMonitor(project_name="Detail")
        web_server.state.runs["detail-1"]["status"] = "complete"
        r = web_client.get("/api/runs/detail-1")
        assert r.status_code == 200
        body = r.json()
        assert body["description"] == "Detail assignment"
        assert body["monitor"] is not None


class TestWebServerResume:
    def test_resume_404_unknown_run(self, web_client: TestClient) -> None:
        r = web_client.post("/api/runs/nope/resume", json={"feedback": "ok"})
        assert r.status_code == 404

    def test_resume_400_not_awaiting(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("r1", "langgraph", "full", "test")
        web_server.state.runs["r1"]["status"] = "running"
        r = web_client.post("/api/runs/r1/resume", json={"feedback": "ok"})
        assert r.status_code == 400

    def test_resume_400_empty_feedback(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("r2", "langgraph", "full", "test")
        web_server.state.set_awaiting_human("r2", {"phase": "awaiting_human"})
        r = web_client.post("/api/runs/r2/resume", json={"feedback": "  "})
        assert r.status_code == 400

    def test_resume_400_wrong_backend(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("r3", "crewai", "full", "test")
        web_server.state.set_awaiting_human("r3", {"phase": "awaiting_human"})
        r = web_client.post("/api/runs/r3/resume", json={"feedback": "ok"})
        assert r.status_code == 400


class TestLanggraphHitlStatus:
    def test_langgraph_hitl_detects_awaiting_human_phase(self) -> None:
        from unittest.mock import MagicMock, patch

        from ai_team.ui.web.server import _langgraph_hitl_status

        snap = MagicMock()
        snap.values = {"current_phase": "awaiting_human", "metadata": {"note": "review"}}
        snap.next = ("human_review",)
        snap.tasks = []

        backend = MagicMock()
        backend._graph_mode.return_value = "placeholder"
        backend._compile_for_run.return_value = MagicMock()

        with patch(
            "ai_team.backends.langgraph_backend.state_inspection.get_thread_state_snapshot",
            return_value=snap,
        ):
            awaiting, payload = _langgraph_hitl_status(backend, "thread-1")

        assert awaiting is True
        assert payload is not None
        assert payload["phase"] == "awaiting_human"
