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

    def test_get_run_includes_spend_and_metrics(self, web_client: TestClient) -> None:
        """SHOWCASE_PLAN 2.3: /api/runs/{id} carries per-run spend + artifact metrics."""
        from ai_team.core.spend_guard import record_usage, reset_spend_guard
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("spend-1", "langgraph", "full", "Spend surfacing")
        reset_spend_guard(5.0, run_id="spend-1")
        record_usage(0.42, total_tokens=999)
        r = web_client.get("/api/runs/spend-1")
        assert r.status_code == 200
        body = r.json()
        assert body["spend"]["spent_usd"] == pytest.approx(0.42)
        assert body["spend"]["total_tokens"] == 999
        assert "metrics" in body  # files/tests/smoke — None-safe when no workspace

    def test_get_run_prefers_stashed_subprocess_spend(self, web_client: TestClient) -> None:
        """CrewAI's spend arrives via its subprocess result payload, not the registry."""
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("spend-2", "crewai", "full", "Subprocess spend")
        web_server.state.runs["spend-2"]["spend"] = {"spent_usd": 1.23, "calls": 7}
        r = web_client.get("/api/runs/spend-2")
        assert r.status_code == 200
        assert r.json()["spend"]["spent_usd"] == 1.23


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


class TestWebServerCancel:
    def test_cancel_running_run_returns_200(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("can-1", "demo", "full", "Cancel test")
        web_server.state.runs["can-1"]["status"] = "running"
        r = web_client.post("/api/runs/can-1/cancel")
        assert r.status_code == 200
        assert r.json()["status"] == "cancelling"

    def test_cancel_unknown_run_returns_404(self, web_client: TestClient) -> None:
        r = web_client.post("/api/runs/nonexistent/cancel")
        assert r.status_code == 404

    def test_cancel_terminal_run_returns_400(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("can-2", "demo", "full", "Already done")
        web_server.state.finish_run("can-2", success=True)
        r = web_client.post("/api/runs/can-2/cancel")
        assert r.status_code == 400

    def test_cancel_sets_flag_and_run_status(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("can-3", "demo", "full", "Flag test")
        web_server.state.runs["can-3"]["status"] = "running"
        web_client.post("/api/runs/can-3/cancel")
        assert web_server.state.runs["can-3"]["status"] == "cancelling"
        assert web_server.state.is_cancel_requested("can-3")

    def test_cancel_already_cancelled_returns_400(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("can-4", "demo", "full", "Already cancelled")
        web_server.state.finish_cancelled("can-4")
        r = web_client.post("/api/runs/can-4/cancel")
        assert r.status_code == 400

    def test_get_run_reports_cancelled_status(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("can-5", "demo", "full", "Get cancelled")
        web_server.state.finish_cancelled("can-5")
        r = web_client.get("/api/runs/can-5")
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    def test_finish_cancelled_sets_finished_at(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("can-6", "demo", "full", "Finish time")
        web_server.state.runs["can-6"]["status"] = "running"
        web_server.state.finish_cancelled("can-6")
        assert web_server.state.runs["can-6"]["finished_at"] is not None
        assert web_server.state.runs["can-6"]["hitl_payload"] is None

    def test_cancel_awaiting_human_run_is_allowed(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("can-7", "langgraph", "full", "HITL cancel")
        web_server.state.set_awaiting_human("can-7", {"phase": "awaiting_human"})
        r = web_client.post("/api/runs/can-7/cancel")
        assert r.status_code == 200


class TestRunStateRemove:
    def test_remove_terminal_run_pops_all_state(self) -> None:
        from ai_team.ui.web.server import RunState

        state = RunState()
        state.create_run("rm-1", "demo", "full", "Remove me")
        state.finish_run("rm-1", success=True)
        state.monitors["rm-1"] = object()
        state.cancel_flags["rm-1"] = False

        state.remove_run("rm-1")

        assert "rm-1" not in state.runs
        assert "rm-1" not in state.monitors
        assert "rm-1" not in state.tasks
        assert "rm-1" not in state.cancel_flags

    def test_remove_non_terminal_run_raises(self) -> None:
        from ai_team.ui.web.server import RunState

        state = RunState()
        state.create_run("rm-2", "demo", "full", "Still running")
        state.runs["rm-2"]["status"] = "running"

        with pytest.raises(ValueError, match="not terminal"):
            state.remove_run("rm-2")
        assert "rm-2" in state.runs

    def test_remove_unknown_run_raises_key_error(self) -> None:
        from ai_team.ui.web.server import RunState

        state = RunState()
        with pytest.raises(KeyError, match="Run not found"):
            state.remove_run("missing")


class TestWebServerRunEstimate:
    def test_run_includes_estimate_usd(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        entry = web_server.state.create_run(
            "est-1", "langgraph", "full", "Test estimate", estimate_usd=0.042
        )
        assert entry["estimate_usd"] == pytest.approx(0.042)

    def test_run_without_estimate_has_none(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        entry = web_server.state.create_run("est-2", "langgraph", "full", "No estimate")
        assert entry["estimate_usd"] is None

    def test_estimate_usd_exposed_in_get_run(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run(
            "est-3", "langgraph", "full", "Expose estimate", estimate_usd=0.1
        )
        r = web_client.get("/api/runs/est-3")
        assert r.status_code == 200
        assert r.json()["estimate_usd"] == pytest.approx(0.1)

    def test_estimate_usd_exposed_in_list_runs(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run(
            "est-4", "langgraph", "full", "List estimate", estimate_usd=0.25
        )
        r = web_client.get("/api/runs")
        assert r.status_code == 200
        run = next(x for x in r.json()["runs"] if x["run_id"] == "est-4")
        assert run["estimate_usd"] == pytest.approx(0.25)

    def test_demo_run_is_sample(self, web_client: TestClient) -> None:
        r = web_client.post("/api/demo")
        assert r.status_code == 200
        run_id = r.json()["run_id"]
        from ai_team.ui.web import server as web_server

        assert web_server.state.runs[run_id]["is_sample"] is True

    def test_is_sample_false_for_regular_run(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        entry = web_server.state.create_run("est-5", "langgraph", "full", "Regular run")
        assert entry["is_sample"] is False

    def test_complexity_stored_on_run(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        entry = web_server.state.create_run(
            "est-6", "langgraph", "full", "Complex run", complexity="complex"
        )
        assert entry["complexity"] == "complex"


class TestWebServerDelete:
    def test_delete_terminal_run_returns_200(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("del-1", "langgraph", "full", "Delete me")
        web_server.state.finish_run("del-1", success=True)
        r = web_client.delete("/api/runs/del-1")
        assert r.status_code == 200
        assert r.json()["deleted"] is True
        assert "del-1" not in web_server.state.runs

    def test_delete_unknown_run_returns_404(self, web_client: TestClient) -> None:
        r = web_client.delete("/api/runs/nonexistent-delete")
        assert r.status_code == 404

    def test_delete_running_run_returns_400(self, web_client: TestClient) -> None:
        from ai_team.ui.web import server as web_server

        web_server.state.create_run("del-2", "langgraph", "full", "Still running")
        web_server.state.runs["del-2"]["status"] = "running"
        r = web_client.delete("/api/runs/del-2")
        assert r.status_code == 400


class TestWebServerBackendsCatalog:
    def test_backends_include_required_key_and_configured(self, web_client: TestClient) -> None:
        r = web_client.get("/api/backends")
        assert r.status_code == 200
        backends = r.json()["backends"]
        assert len(backends) == 3
        for b in backends:
            assert "required_key" in b
            assert "configured" in b
            assert isinstance(b["configured"], bool)


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

    def test_hitl_status_survives_independent_recompile_with_persistent_path(
        self, tmp_path, monkeypatch
    ) -> None:
        """Regression: the web server compiles the graph twice per run (once to
        stream events, once in _langgraph_hitl_status to read back state). Each
        compile's checkpointer defaults to a throwaway in-memory SQLite DB when
        AI_TEAM_LANGGRAPH_SQLITE_PATH is unset, so the status-check compile could
        never see the streaming compile's checkpoints — a run that actually
        paused on human_review silently reported "complete" via the web API
        instead of "awaiting_human". Verifies a real langgraph interrupt()
        written by one compile is visible to a second, independent compile once
        both point at the same persistent file (as the web server now defaults
        it to — see server.py module-level os.environ.setdefault).

        Uses a minimal standalone graph wrapping the real
        _node_human_review_full node (the one production uses, which actually
        calls interrupt()) instead of driving the full LLM pipeline — isolates
        the checkpointer-sharing mechanism without needing API keys.
        """
        from ai_team.backends.langgraph_backend.checkpointer import resolve_sqlite_checkpointer
        from ai_team.backends.langgraph_backend.graphs.main_graph import _node_human_review_full
        from ai_team.backends.langgraph_backend.graphs.state import LangGraphProjectState
        from ai_team.backends.langgraph_backend.state_inspection import get_thread_state_snapshot
        from langgraph.graph import END, START, StateGraph

        db_path = str(tmp_path / "checkpoints.sqlite")
        monkeypatch.setenv("AI_TEAM_LANGGRAPH_SQLITE_PATH", db_path)
        thread_id = "hitl-regression-thread"

        def _build() -> object:
            g = StateGraph(LangGraphProjectState)
            g.add_node("human_review", _node_human_review_full)
            g.add_edge(START, "human_review")
            g.add_edge("human_review", END)
            return g.compile(checkpointer=resolve_sqlite_checkpointer())

        init = {
            "project_description": "x" * 20,
            "project_id": thread_id,
            "current_phase": "planning",
            "metadata": {"testing_needs_human": True},
        }
        # First compile: run to the interrupt (invoke returns once paused).
        _build().invoke(init, {"configurable": {"thread_id": thread_id}})

        # Second, fully independent compile+checkpointer — mirrors
        # _langgraph_hitl_status building its own graph in a separate call.
        # A mid-node interrupt() pauses *before* the node's return executes, so
        # current_phase still reads its pre-interrupt value ("planning") — the
        # actual pause signal LangGraph records is a pending interrupt on the
        # next task, which is exactly the second detection path
        # _langgraph_hitl_status falls back to (snap.tasks[].interrupts).
        checker_graph = _build()
        snap = get_thread_state_snapshot(checker_graph, thread_id)

        assert snap.tasks, "a fresh compile sharing the persistent path must see the paused task"
        interrupts = [getattr(t, "interrupts", None) for t in snap.tasks]
        assert any(interrupts), (
            "the interrupt() written by a different compile must be visible "
            "to an independently constructed graph over the same file"
        )

    def test_server_module_defaults_to_persistent_sqlite_path(self) -> None:
        """server.py must default AI_TEAM_LANGGRAPH_SQLITE_PATH to a real file,
        not leave it unset (which falls back to a throwaway :memory: DB per
        compile — the root cause this class regression-tests).
        """
        import os

        path = os.environ.get("AI_TEAM_LANGGRAPH_SQLITE_PATH")
        assert path, "ai_team.ui.web.server must set a default persistent checkpoint path"
        assert path != ":memory:"
