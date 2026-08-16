"""Content-addressed blob store and TraceStore (R1.4, R1.7, R2)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from evals.trace.models import Trace
from evals.trace.schema import TraceSchemaError, migrate_trace_dict

_TEXT_TRUNCATE_BYTES = 256 * 1024
_TRUNCATION_MARKER = b"\n[TRUNCATED at 256KB]"

_DEFAULT_ROOT = Path("evals/traces")


class TraceExistsError(FileExistsError):
    """Raised when writing a trace_id that already has a document on disk."""


@dataclass(frozen=True)
class TraceIndexRow:
    """Denormalized index row for sampling and corpus queries."""

    trace_id: str
    scenario_id: str
    backend: str
    status: str
    git_sha: str
    started_at: str
    duration_s: float | None
    cost_usd: float | None
    cost_source: str
    span_count: int
    error_count: int
    retry_count: int
    file_count: int
    label_count: int
    tier: str | None
    schema_version: int


def _blobs_root(root: Path) -> Path:
    return root / "blobs"


def put_blob(data: bytes, *, root: Path | None = None) -> str:
    """Store *data* content-addressed under ``evals/traces/blobs/<sha[:2]>/<sha>``.

    Text payloads larger than 256 KB are truncated with a trailing marker before
    hashing. Non-UTF-8 (binary) payloads store metadata only — no bytes on disk —
    and return the sha256 of the original bytes so callers can still inventory them.

    Args:
        data: Raw file bytes.
        root: Trace corpus root (default ``evals/traces``).

    Returns:
        Hex sha256 of the (possibly truncated) stored content, or of the original
        bytes when the payload is binary-only.
    """
    base = root or _DEFAULT_ROOT
    try:
        data.decode("utf-8")
        is_text = True
    except UnicodeDecodeError:
        is_text = False

    if not is_text:
        sha = hashlib.sha256(data).hexdigest()
        meta_dir = _blobs_root(base) / sha[:2]
        meta_dir.mkdir(parents=True, exist_ok=True)
        meta_path = meta_dir / f"{sha}.meta.json"
        if not meta_path.exists():
            meta_path.write_text(
                json.dumps({"sha256": sha, "size_bytes": len(data), "binary": True}),
                encoding="utf-8",
            )
        return sha

    stored = data
    if len(stored) > _TEXT_TRUNCATE_BYTES:
        stored = stored[:_TEXT_TRUNCATE_BYTES] + _TRUNCATION_MARKER

    sha = hashlib.sha256(stored).hexdigest()
    dest_dir = _blobs_root(base) / sha[:2]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / sha
    if not dest.exists():
        dest.write_bytes(stored)
    return sha


def get_blob(sha: str, *, root: Path | None = None) -> bytes | None:
    """Return blob bytes for *sha*, or None for missing / binary-only entries."""
    base = root or _DEFAULT_ROOT
    path = _blobs_root(base) / sha[:2] / sha
    if path.is_file():
        return path.read_bytes()
    return None


class TraceStore:
    """Append-only trace documents plus a SQLite query index."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else _DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        (_blobs_root(self.root)).mkdir(parents=True, exist_ok=True)
        self._db_path = self.root / "index.db"

    def write(self, trace: Trace) -> Path:
        """Persist *trace* as JSON. Refuses overwrite (R1.7)."""
        path = self.root / f"{trace.trace_id}.json"
        if path.exists():
            raise TraceExistsError(f"trace already exists: {trace.trace_id}")
        path.write_text(trace.model_dump_json(indent=2), encoding="utf-8")
        self._upsert_index_row(trace)
        return path

    def load(self, trace_id: str) -> Trace:
        """Load and migrate a trace document by id."""
        path = self.root / f"{trace_id}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        migrated = migrate_trace_dict(raw)
        return Trace.model_validate(migrated)

    def put_blob(self, data: bytes) -> str:
        """Store a blob under this store's root."""
        return put_blob(data, root=self.root)

    def get_blob(self, sha: str) -> bytes | None:
        """Fetch a blob under this store's root."""
        return get_blob(sha, root=self.root)

    def rebuild_index(self) -> int:
        """Rebuild the SQLite index from ``*.json`` traces. Idempotent (WAL)."""
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("DROP TABLE IF EXISTS traces")
            self._ensure_schema(conn)
            count = 0
            for path in sorted(self.root.glob("*.json")):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    migrated = migrate_trace_dict(raw)
                    trace = Trace.model_validate(migrated)
                except (OSError, json.JSONDecodeError, TraceSchemaError, ValueError):
                    continue
                self._upsert_index_row(trace, conn=conn)
                count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    def query(self, **filters: Any) -> list[TraceIndexRow]:
        """Return index rows matching equality filters on column names."""
        conn = self._connect()
        try:
            self._ensure_schema(conn)
            clauses: list[str] = []
            params: list[Any] = []
            for key, value in filters.items():
                if value is None:
                    continue
                clauses.append(f"{key} = ?")
                params.append(value)
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = conn.execute(
                f"SELECT * FROM traces{where} ORDER BY started_at",  # noqa: S608
                params,
            ).fetchall()
            return [self._row_from_sql(r) for r in rows]
        finally:
            conn.close()

    def stats(self) -> list[tuple[str, str, str, int]]:
        """Return ``(backend, scenario_id, status, count)`` aggregates."""
        conn = self._connect()
        try:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT backend, scenario_id, status, COUNT(*) AS n
                FROM traces
                GROUP BY backend, scenario_id, status
                ORDER BY backend, scenario_id, status
                """
            ).fetchall()
            return [(str(r[0]), str(r[1]), str(r[2]), int(r[3])) for r in rows]
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _ensure_schema(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS traces (
              trace_id TEXT PRIMARY KEY,
              scenario_id TEXT,
              backend TEXT,
              status TEXT,
              git_sha TEXT,
              started_at TEXT,
              duration_s REAL,
              cost_usd REAL,
              cost_source TEXT,
              span_count INT,
              error_count INT,
              retry_count INT,
              file_count INT,
              label_count INT DEFAULT 0,
              tier TEXT,
              schema_version INT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_traces_strata " "ON traces(backend, scenario_id, status)"
        )
        conn.commit()

    def _upsert_index_row(self, trace: Trace, *, conn: sqlite3.Connection | None = None) -> None:
        own = conn is None
        db = conn or self._connect()
        try:
            if own:
                self._ensure_schema(db)
            duration: float | None = None
            if trace.ended_at is not None:
                duration = (trace.ended_at - trace.started_at).total_seconds()
            started = (
                trace.started_at.isoformat()
                if isinstance(trace.started_at, datetime)
                else str(trace.started_at)
            )
            db.execute(
                """
                INSERT INTO traces (
                  trace_id, scenario_id, backend, status, git_sha, started_at,
                  duration_s, cost_usd, cost_source, span_count, error_count,
                  retry_count, file_count, label_count, tier, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trace_id) DO UPDATE SET
                  scenario_id=excluded.scenario_id,
                  backend=excluded.backend,
                  status=excluded.status,
                  git_sha=excluded.git_sha,
                  started_at=excluded.started_at,
                  duration_s=excluded.duration_s,
                  cost_usd=excluded.cost_usd,
                  cost_source=excluded.cost_source,
                  span_count=excluded.span_count,
                  error_count=excluded.error_count,
                  retry_count=excluded.retry_count,
                  file_count=excluded.file_count,
                  tier=excluded.tier,
                  schema_version=excluded.schema_version
                """,
                (
                    trace.trace_id,
                    trace.scenario_id,
                    trace.backend,
                    trace.status,
                    trace.provenance.git_sha,
                    started,
                    duration,
                    trace.cost.usd,
                    trace.cost.source,
                    len(trace.spans),
                    len(trace.errors()),
                    len(trace.spans_of("retry")),
                    len(trace.artifacts),
                    0,
                    trace.provenance.tier,
                    trace.schema_version,
                ),
            )
            if own:
                db.commit()
        finally:
            if own:
                db.close()

    @staticmethod
    def _row_from_sql(row: sqlite3.Row) -> TraceIndexRow:
        return TraceIndexRow(
            trace_id=row["trace_id"],
            scenario_id=row["scenario_id"],
            backend=row["backend"],
            status=row["status"],
            git_sha=row["git_sha"],
            started_at=row["started_at"],
            duration_s=row["duration_s"],
            cost_usd=row["cost_usd"],
            cost_source=row["cost_source"],
            span_count=row["span_count"],
            error_count=row["error_count"],
            retry_count=row["retry_count"],
            file_count=row["file_count"],
            label_count=row["label_count"],
            tier=row["tier"],
            schema_version=row["schema_version"],
        )
