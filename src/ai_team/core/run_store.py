"""SQLite-backed persistence for web-UI run and comparison records.

``RunState`` in ``ui.web.server`` tracks active/completed runs in memory only,
so every server restart wipes run history — the exact gap that made a real,
in-flight 3-way Compare run disappear from ``/api/runs`` mid-session. ``RunStore``
mirrors run lifecycle events into ``data/memory.db`` (the same SQLite file
``ai_team.memory.memory_config.LongTermStore`` uses) so runs survive restarts and
are queryable. Independent of ``MemorySettings.memory_enabled`` — run history
should persist regardless of whether agent long-term memory is on.

Comparison runs (Compare tab "Run All Backends") share a client-generated
``comparison_id`` across their three independent ``/ws/run`` connections; this
module also tracks that grouping so a comparison's three backend runs can be
looked up together after the fact.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Shared in-memory connection so multiple RunStore instances against ":memory:"
# (tests) see the same DB, mirroring memory_config._get_sqlite_connection.
_shared_memory_conn: sqlite3.Connection | None = None


def _get_sqlite_connection(path: str) -> sqlite3.Connection:
    global _shared_memory_conn
    if path == ":memory:":
        if _shared_memory_conn is None:
            _shared_memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
        return _shared_memory_conn
    return sqlite3.connect(path, check_same_thread=False)


def _ensure_parent(path: str) -> None:
    if path != ":memory:" and not path.startswith("file:"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)


class RunStore:
    """Persists run and comparison records to SQLite.

    All writes are best-effort: a persistence failure logs a warning and never
    raises, so a DB hiccup can't take down a live run the way an unhandled
    exception in ``RunState`` would.
    """

    def __init__(self, sqlite_path: str) -> None:
        self._path = sqlite_path
        _ensure_parent(sqlite_path)
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
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                comparison_id TEXT,
                backend TEXT NOT NULL,
                profile TEXT NOT NULL,
                description TEXT NOT NULL,
                complexity TEXT,
                status TEXT NOT NULL,
                is_sample INTEGER NOT NULL DEFAULT 0,
                estimate_usd REAL,
                error TEXT,
                result_json TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS comparison_runs (
                comparison_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                backend TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (comparison_id, run_id)
            );
            CREATE INDEX IF NOT EXISTS idx_runs_comparison ON runs(comparison_id);
            CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
            CREATE INDEX IF NOT EXISTS idx_comparison_runs_comparison
                ON comparison_runs(comparison_id);
        """)

    def upsert_run(
        self,
        run_id: str,
        *,
        backend: str,
        profile: str,
        description: str,
        complexity: str | None = None,
        status: str = "pending",
        is_sample: bool = False,
        estimate_usd: float | None = None,
        comparison_id: str | None = None,
        started_at: str | None = None,
    ) -> None:
        """Insert a new run record (called once, at ``create_run`` time)."""
        now = datetime.now(UTC).isoformat()
        try:
            with self._with_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO runs
                        (run_id, comparison_id, backend, profile, description,
                         complexity, status, is_sample, estimate_usd,
                         started_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        comparison_id = excluded.comparison_id,
                        status = excluded.status,
                        updated_at = excluded.updated_at
                    """,
                    (
                        run_id,
                        comparison_id,
                        backend,
                        profile,
                        description,
                        complexity,
                        status,
                        1 if is_sample else 0,
                        estimate_usd,
                        started_at or now,
                        now,
                    ),
                )
                if comparison_id:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO comparison_runs
                            (comparison_id, run_id, backend, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (comparison_id, run_id, backend, now),
                    )
        except Exception as e:  # noqa: BLE001 - persistence must never break a run
            logger.warning("run_store_upsert_failed", run_id=run_id, error=str(e))

    def update_status(
        self,
        run_id: str,
        status: str,
        *,
        error: str | None = None,
        finished: bool = False,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Update a run's status (running/complete/error/cancelled/awaiting_human)."""
        now = datetime.now(UTC).isoformat()
        try:
            with self._with_conn() as conn:
                if finished:
                    conn.execute(
                        """
                        UPDATE runs
                        SET status = ?, error = ?, result_json = ?,
                            finished_at = ?, updated_at = ?
                        WHERE run_id = ?
                        """,
                        (
                            status,
                            error,
                            json.dumps(result, default=str) if result is not None else None,
                            now,
                            now,
                            run_id,
                        ),
                    )
                else:
                    conn.execute(
                        "UPDATE runs SET status = ?, error = ?, updated_at = ? WHERE run_id = ?",
                        (status, error, now, run_id),
                    )
        except Exception as e:  # noqa: BLE001 - persistence must never break a run
            logger.warning("run_store_update_failed", run_id=run_id, error=str(e))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = cur.fetchone()
        return dict(row) if row else None

    def list_runs(self, limit: int = 200) -> list[dict[str, Any]]:
        """Recent runs, newest first — the persisted equivalent of GET /api/runs."""
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_comparison(self, comparison_id: str) -> list[dict[str, Any]]:
        """All runs belonging to one comparison, in the order they were created."""
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """
                SELECT runs.* FROM runs
                JOIN comparison_runs ON comparison_runs.run_id = runs.run_id
                WHERE comparison_runs.comparison_id = ?
                ORDER BY runs.started_at ASC
                """,
                (comparison_id,),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def list_comparisons(self, limit: int = 50) -> list[dict[str, Any]]:
        """Most recent comparison_ids with their run count and earliest start time."""
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """
                SELECT comparison_runs.comparison_id AS comparison_id,
                       COUNT(*) AS run_count,
                       MIN(runs.started_at) AS started_at
                FROM comparison_runs
                JOIN runs ON runs.run_id = comparison_runs.run_id
                GROUP BY comparison_runs.comparison_id
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]
