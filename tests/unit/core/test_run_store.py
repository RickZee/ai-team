"""Unit tests for RunStore (SQLite-backed run/comparison persistence).

Regression context: RunState in ui.web.server tracked runs in memory only, so
a server restart wiped all run history — a genuinely in-flight run vanished
from GET /api/runs mid-session because a stale server process was still
serving requests from before a restart. RunStore mirrors run lifecycle events
into data/memory.db so history survives restarts and is queryable, and tracks
which runs belong to the same Compare-tab session (comparison_id).
"""

from __future__ import annotations

from ai_team.core.run_store import RunStore


def _store() -> RunStore:
    # Each test gets its own dedicated in-memory DB (unlike the shared-conn
    # ":memory:" path used for production parity in memory_config, tests need
    # isolation from each other).
    import sqlite3

    from ai_team.core import run_store as run_store_module

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    store = RunStore.__new__(RunStore)
    store._path = ":memory:"
    run_store_module._shared_memory_conn = conn
    store._init_schema()
    return store


class TestRunLifecycle:
    def test_upsert_creates_pending_run(self) -> None:
        store = _store()
        store.upsert_run(
            "run-1", backend="langgraph", profile="full", description="build a todo app"
        )
        row = store.get_run("run-1")
        assert row is not None
        assert row["status"] == "pending"
        assert row["backend"] == "langgraph"
        assert row["finished_at"] is None

    def test_update_status_running(self) -> None:
        store = _store()
        store.upsert_run("run-1", backend="crewai", profile="full", description="x")
        store.update_status("run-1", "running")
        row = store.get_run("run-1")
        assert row["status"] == "running"
        assert row["finished_at"] is None

    def test_update_status_finished_sets_timestamp_and_result(self) -> None:
        store = _store()
        store.upsert_run("run-1", backend="claude-agent-sdk", profile="full", description="x")
        store.update_status(
            "run-1", "complete", finished=True, result={"success": True, "tests": 43}
        )
        row = store.get_run("run-1")
        assert row["status"] == "complete"
        assert row["finished_at"] is not None
        assert '"tests": 43' in row["result_json"]

    def test_update_status_error_records_message(self) -> None:
        store = _store()
        store.upsert_run("run-1", backend="crewai", profile="full", description="x")
        store.update_status("run-1", "error", error="guardrail deadlock", finished=True)
        row = store.get_run("run-1")
        assert row["status"] == "error"
        assert row["error"] == "guardrail deadlock"

    def test_get_run_missing_returns_none(self) -> None:
        store = _store()
        assert store.get_run("does-not-exist") is None

    def test_list_runs_newest_first(self) -> None:
        store = _store()
        store.upsert_run(
            "run-a",
            backend="langgraph",
            profile="full",
            description="x",
            started_at="2026-07-01T10:00:00Z",
        )
        store.upsert_run(
            "run-b",
            backend="crewai",
            profile="full",
            description="x",
            started_at="2026-07-01T11:00:00Z",
        )
        rows = store.list_runs()
        assert [r["run_id"] for r in rows] == ["run-b", "run-a"]

    def test_upsert_is_idempotent_on_conflict(self) -> None:
        store = _store()
        store.upsert_run("run-1", backend="langgraph", profile="full", description="x")
        store.upsert_run(
            "run-1", backend="langgraph", profile="full", description="x", status="running"
        )
        rows = store.list_runs()
        assert len(rows) == 1
        assert rows[0]["status"] == "running"


class TestComparisonGrouping:
    def test_comparison_id_links_three_backends(self) -> None:
        store = _store()
        cid = "cmp-123"
        for backend in ("crewai", "langgraph", "claude-agent-sdk"):
            store.upsert_run(
                f"run-{backend}",
                backend=backend,
                profile="full",
                description="build a todo app",
                comparison_id=cid,
            )
        rows = store.get_comparison(cid)
        assert {r["backend"] for r in rows} == {"crewai", "langgraph", "claude-agent-sdk"}

    def test_comparison_survives_status_updates(self) -> None:
        store = _store()
        cid = "cmp-456"
        store.upsert_run(
            "run-1", backend="langgraph", profile="full", description="x", comparison_id=cid
        )
        store.update_status("run-1", "complete", finished=True)
        rows = store.get_comparison(cid)
        assert len(rows) == 1
        assert rows[0]["status"] == "complete"

    def test_get_comparison_unknown_id_returns_empty(self) -> None:
        store = _store()
        assert store.get_comparison("no-such-comparison") == []

    def test_list_comparisons_groups_by_id(self) -> None:
        store = _store()
        store.upsert_run(
            "run-1", backend="langgraph", profile="full", description="x", comparison_id="cmp-1"
        )
        store.upsert_run(
            "run-2", backend="crewai", profile="full", description="x", comparison_id="cmp-1"
        )
        store.upsert_run(
            "run-3", backend="langgraph", profile="full", description="y", comparison_id="cmp-2"
        )
        comparisons = store.list_comparisons()
        by_id = {c["comparison_id"]: c["run_count"] for c in comparisons}
        assert by_id == {"cmp-1": 2, "cmp-2": 1}

    def test_run_without_comparison_id_not_grouped(self) -> None:
        store = _store()
        store.upsert_run("solo-run", backend="langgraph", profile="full", description="x")
        assert store.list_comparisons() == []


class TestPersistenceFailureIsolation:
    def test_upsert_on_closed_store_does_not_raise(self) -> None:
        """A persistence-layer error must never propagate into the caller —
        RunState.create_run must not fail just because the DB write failed.
        """
        store = _store()
        store._path = "/nonexistent/deeply/nested/path/that/cannot/be/created.db"
        # Should log a warning and return, not raise.
        store.upsert_run("run-1", backend="langgraph", profile="full", description="x")

    def test_update_status_on_broken_store_does_not_raise(self) -> None:
        store = _store()
        store.upsert_run("run-1", backend="langgraph", profile="full", description="x")
        store._path = "/nonexistent/deeply/nested/path/that/cannot/be/created.db"
        store.update_status("run-1", "error", error="boom", finished=True)
