"""Unit tests for ``LongTermStore`` in ``memory_config`` (file-backed SQLite for isolation)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from ai_team.memory.memory_config import LongTermStore


@pytest.fixture
def sqlite_path(tmp_path: Path) -> str:
    return str(tmp_path / "ltm.sqlite")


class TestLongTermStoreConversations:
    def test_add_and_retrieve_conversation(self, sqlite_path: str) -> None:
        store = LongTermStore(sqlite_path=sqlite_path, retention_days=365)
        rid = store.add_conversation("user", "hello", project_id="p1")
        assert rid
        rows = store.get_recent_conversations(limit=10, project_id="p1")
        assert len(rows) == 1
        assert rows[0]["content"] == "hello"
        assert rows[0]["role"] == "user"

    def test_filter_by_project_id(self, sqlite_path: str) -> None:
        store = LongTermStore(sqlite_path=sqlite_path, retention_days=365)
        store.add_conversation("user", "a", project_id="pa")
        store.add_conversation("user", "b", project_id="pb")
        pa = store.get_recent_conversations(limit=10, project_id="pa")
        assert len(pa) == 1
        assert pa[0]["content"] == "a"

    def test_limit_respected(self, sqlite_path: str) -> None:
        store = LongTermStore(sqlite_path=sqlite_path, retention_days=365)
        for i in range(5):
            store.add_conversation("user", str(i), project_id="p")
        rows = store.get_recent_conversations(limit=2, project_id="p")
        assert len(rows) == 2


class TestLongTermStoreMetrics:
    def test_add_metric(self, sqlite_path: str) -> None:
        store = LongTermStore(sqlite_path=sqlite_path, retention_days=365)
        store.add_metric("architect", "m1", "latency_ms", 12.5)
        summary = store.get_metrics_summary()
        assert any(s["agent_role"] == "architect" for s in summary)

    def test_get_metrics_summary_aggregation(self, sqlite_path: str) -> None:
        store = LongTermStore(sqlite_path=sqlite_path, retention_days=365)
        store.add_metric("dev", "m", "tokens", 10.0)
        store.add_metric("dev", "m", "tokens", 20.0)
        summary = store.get_metrics_summary()
        row = next(s for s in summary if s["metric_name"] == "tokens")
        assert row["count"] == 2
        assert row["avg_value"] == 15.0


class TestLongTermStorePatterns:
    def test_add_and_get_patterns(self, sqlite_path: str) -> None:
        store = LongTermStore(sqlite_path=sqlite_path, retention_days=365)
        pid = store.add_pattern("arch", "use postgres")
        assert pid
        patterns = store.get_patterns()
        assert any(p["content"] == "use postgres" for p in patterns)

    def test_filter_by_pattern_type(self, sqlite_path: str) -> None:
        store = LongTermStore(sqlite_path=sqlite_path, retention_days=365)
        store.add_pattern("style", "black")
        store.add_pattern("arch", "ddd")
        only = store.get_patterns(pattern_type="arch")
        assert all(p["pattern_type"] == "arch" for p in only)


class TestLongTermStoreRetention:
    def test_apply_retention_deletes_old_rows(self, sqlite_path: str) -> None:
        store = LongTermStore(sqlite_path=sqlite_path, retention_days=0)
        store.add_conversation("user", "old", project_id="p")
        # Force created_at into the past
        with store._with_conn() as conn:  # noqa: SLF001
            past = (datetime.now(UTC) - timedelta(days=400)).isoformat()
            conn.execute("UPDATE conversations SET created_at = ?", (past,))
        deleted = store.apply_retention()
        assert deleted >= 1
        assert store.get_recent_conversations(limit=10, project_id="p") == []

    def test_apply_retention_preserves_recent(self, sqlite_path: str) -> None:
        store = LongTermStore(sqlite_path=sqlite_path, retention_days=90)
        store.add_conversation("user", "fresh", project_id="p")
        assert store.apply_retention() == 0
        assert store.get_recent_conversations(limit=5, project_id="p")


class TestLongTermStoreSchema:
    def test_idempotent_schema_init(self, sqlite_path: str) -> None:
        LongTermStore(sqlite_path=sqlite_path, retention_days=1)
        LongTermStore(sqlite_path=sqlite_path, retention_days=1)
        store = LongTermStore(sqlite_path=sqlite_path, retention_days=1)
        assert store.add_conversation("u", "x") is not None
