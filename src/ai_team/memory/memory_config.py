"""
Long-term memory store (SQLite).

Cross-project persistence for failure records, learned lessons, and run
metrics — the substrate for the lessons/self-improvement loop
(:mod:`ai_team.memory.lessons`). Short-term ChromaDB memory and the
MemoryManager facade were removed with the memory-subsystem merge
(SHOWCASE_PLAN 3.5); file-based handoff plus this store is the memory model.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager, suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import structlog

logger = structlog.get_logger(__name__)

MemoryType = Literal["long_term"]


def _get_sqlite_connection(path: str) -> sqlite3.Connection:
    """Return a connection. For :memory:, reuse one shared connection so both stores see same DB."""
    global _shared_memory_conn
    if path == ":memory:":
        if _shared_memory_conn is None:
            _shared_memory_conn = sqlite3.connect(":memory:")
        return _shared_memory_conn
    return sqlite3.connect(path)


def _sqlite_path_for_schema(path: str) -> str:
    """Path/uri for schema and connection. :memory: stays as-is for shared conn."""
    if path != ":memory:" and not path.startswith("file:"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


class LongTermStore:
    """
    SQLite-backed store for conversation history, agent performance metrics,
    and learned patterns. Retention applied by created_at and retention_days.
    """

    def __init__(self, sqlite_path: str, retention_days: int) -> None:
        self._path = sqlite_path
        _sqlite_path_for_schema(sqlite_path)
        self._retention_days = retention_days
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        return _get_sqlite_connection(self._path)

    @contextmanager
    def _with_conn(self) -> Any:
        conn = self._conn()
        try:
            yield conn
        finally:
            with suppress(Exception):
                conn.commit()
            if self._path != ":memory:":
                conn.close()

    def _init_schema(self) -> None:
        with self._with_conn() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_role TEXT NOT NULL,
                model TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                value REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_conv_project ON conversations(project_id);
            CREATE INDEX IF NOT EXISTS idx_conv_created ON conversations(created_at);
            CREATE INDEX IF NOT EXISTS idx_metrics_created ON performance_metrics(created_at);
            CREATE INDEX IF NOT EXISTS idx_patterns_created ON learned_patterns(created_at);
        """)

    def add_conversation(
        self,
        role: str,
        content: str,
        project_id: str | None = None,
    ) -> str:
        """Append a conversation turn. Returns row id."""
        row_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        with self._with_conn() as conn:
            conn.execute(
                "INSERT INTO conversations (id, project_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (row_id, project_id or "", role, content, now),
            )
        return row_id

    def add_metric(self, agent_role: str, model: str, metric_name: str, value: float) -> None:
        """Record an agent performance metric."""
        now = datetime.now(UTC).isoformat()
        with self._with_conn() as conn:
            conn.execute(
                "INSERT INTO performance_metrics (agent_role, model, metric_name, value, created_at) VALUES (?, ?, ?, ?, ?)",
                (agent_role, model, metric_name, value, now),
            )

    def add_pattern(self, pattern_type: str, content: str) -> str:
        """Store a learned pattern (e.g. architecture decision, code pattern). Returns id."""
        row_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        with self._with_conn() as conn:
            conn.execute(
                "INSERT INTO learned_patterns (id, pattern_type, content, created_at) VALUES (?, ?, ?, ?)",
                (row_id, pattern_type, content, now),
            )
        return row_id

    def get_recent_conversations(
        self,
        limit: int = 50,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch recent conversation turns, optionally filtered by project."""
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            if project_id:
                cur = conn.execute(
                    "SELECT id, project_id, role, content, created_at FROM conversations WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                    (project_id, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT id, project_id, role, content, created_at FROM conversations ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_metrics_summary(self) -> list[dict[str, Any]]:
        """Aggregate performance metrics by role/model for tuning."""
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("""
                SELECT agent_role, model, metric_name, AVG(value) as avg_value, COUNT(*) as count
                FROM performance_metrics
                GROUP BY agent_role, model, metric_name
            """)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_metrics_timeseries(
        self, metric_name: str | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        """Return raw metric rows ordered by time (oldest first) for trend analysis.

        Unlike :meth:`get_metrics_summary`, this preserves the per-run sequence so
        callers can answer "is the system improving over time?" rather than only
        "what is the average?".
        """
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            if metric_name:
                cur = conn.execute(
                    "SELECT agent_role, model, metric_name, value, created_at "
                    "FROM performance_metrics WHERE metric_name = ? "
                    "ORDER BY created_at ASC LIMIT ?",
                    (metric_name, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT agent_role, model, metric_name, value, created_at "
                    "FROM performance_metrics ORDER BY created_at ASC LIMIT ?",
                    (limit,),
                )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_patterns(
        self, pattern_type: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Retrieve learned patterns, optionally by type."""
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            if pattern_type:
                cur = conn.execute(
                    "SELECT id, pattern_type, content, created_at FROM learned_patterns WHERE pattern_type = ? ORDER BY created_at DESC LIMIT ?",
                    (pattern_type, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT id, pattern_type, content, created_at FROM learned_patterns ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def apply_retention(self) -> int:
        """Delete entries older than retention_days. Returns number of rows deleted."""
        cutoff = (datetime.now(UTC) - timedelta(days=self._retention_days)).isoformat()
        deleted = 0
        with self._with_conn() as conn:
            for table in ("conversations", "performance_metrics", "learned_patterns"):
                cur = conn.execute(f"DELETE FROM {table} WHERE created_at < ?", (cutoff,))
                deleted += cur.rowcount
        if deleted:
            logger.info("long_term_retention_applied", deleted=deleted, cutoff=cutoff)
        return deleted


# -----------------------------------------------------------------------------
# Entity store — project entities and relationships
# -----------------------------------------------------------------------------
