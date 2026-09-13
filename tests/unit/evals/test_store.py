"""Tests for blob store and TraceStore write/load (tasks 1.3, 1.5)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals.provenance import Provenance
from evals.store import TraceExistsError, TraceStore, get_blob, put_blob
from evals.trace.models import SCHEMA_VERSION, CostRecord, Span, Trace
from evals.trace.schema import TraceSchemaError, migrate_trace_dict

pytestmark = pytest.mark.eval_unit


def _minimal_trace(trace_id: str = "t1") -> Trace:
    t0 = datetime(2026, 8, 1, tzinfo=UTC)
    return Trace(
        schema_version=SCHEMA_VERSION,
        trace_id=trace_id,
        scenario_id="smoke-test",
        backend="crewai",
        status="complete",
        started_at=t0,
        ended_at=t0,
        spans=[Span(span_id="span_0000", type="phase_start", t_start=t0, phase="planning")],
        artifacts=[],
        cost=CostRecord(usd=0.0, input_tokens=0, output_tokens=0, source="unknown"),
        provenance=Provenance(
            git_sha="abc",
            git_dirty=False,
            python_version="3.12",
            platform="test",
            harness_version="0.1.0",
            taxonomy_version="1.0.0",
            pricing_table_version="unset",
        ),
    )


def test_put_blob_deduplicates(tmp_path: Path) -> None:
    root = tmp_path / "traces"
    a = put_blob(b"hello world", root=root)
    b = put_blob(b"hello world", root=root)
    assert a == b
    blob_files = list((root / "blobs").rglob("*"))
    content_files = [p for p in blob_files if p.is_file() and not p.name.endswith(".meta.json")]
    assert len(content_files) == 1
    assert get_blob(a, root=root) == b"hello world"


def test_put_blob_truncates_large_text(tmp_path: Path) -> None:
    root = tmp_path / "traces"
    payload = ("x" * (1024 * 1024)).encode("utf-8")
    sha = put_blob(payload, root=root)
    stored = get_blob(sha, root=root)
    assert stored is not None
    assert len(stored) < len(payload)
    assert stored.endswith(b"\n[TRUNCATED at 256KB]")


def test_put_blob_binary_stores_metadata_only(tmp_path: Path) -> None:
    root = tmp_path / "traces"
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\xff" * 100
    sha = put_blob(png, root=root)
    assert get_blob(sha, root=root) is None
    meta = root / "blobs" / sha[:2] / f"{sha}.meta.json"
    assert meta.is_file()
    assert json.loads(meta.read_text())["binary"] is True


def test_trace_store_refuses_overwrite(tmp_path: Path) -> None:
    store = TraceStore(root=tmp_path / "traces")
    store.write(_minimal_trace("dup"))
    with pytest.raises(TraceExistsError):
        store.write(_minimal_trace("dup"))


def test_load_future_schema_raises_migration_message(tmp_path: Path) -> None:
    store = TraceStore(root=tmp_path / "traces")
    path = store.root / "future.json"
    doc = _minimal_trace("future").model_dump(mode="json")
    doc["schema_version"] = 99
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(TraceSchemaError, match="migration"):
        store.load("future")


def test_migrate_unknown_future_version() -> None:
    with pytest.raises(TraceSchemaError, match="migration"):
        migrate_trace_dict({"schema_version": 99, "trace_id": "x"})


def test_migrate_v1_to_v2_adds_arm_id() -> None:
    migrated = migrate_trace_dict({"schema_version": 1, "trace_id": "old"})
    assert migrated["schema_version"] == SCHEMA_VERSION
    assert migrated["arm_id"] is None
