"""Round-trip and schema tests for Trace models (task 1.1)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from evals.provenance import Provenance
from evals.trace.models import SCHEMA_VERSION, Artifact, CostRecord, Span, Trace

pytestmark = pytest.mark.eval_unit


def _sample_trace() -> Trace:
    t0 = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 1, 12, 0, 5, tzinfo=UTC)
    t2 = datetime(2026, 8, 1, 12, 1, 0, tzinfo=UTC)
    spans = [
        Span(
            span_id="span_0000",
            type="phase_start",
            t_start=t0,
            t_end=t0,
            phase="planning",
            agent_role="product_owner",
        ),
        Span(
            span_id="span_0001",
            type="tool_use",
            t_start=t1,
            t_end=t1,
            phase="development",
            agent_role="fullstack_developer",
            payload={"tool": "file_writer", "path": "src/app.py"},
        ),
        Span(
            span_id="span_0002",
            type="error",
            t_start=t2,
            t_end=t2,
            phase="testing",
            payload={"message": "AssertionError"},
        ),
    ]
    return Trace(
        schema_version=SCHEMA_VERSION,
        trace_id="smoke-test__crewai__20260801T120000Z__abcd",
        scenario_id="smoke-test",
        backend="crewai",
        status="complete",
        started_at=t0,
        ended_at=t2,
        spans=spans,
        artifacts=[
            Artifact(
                path="src/app.py",
                size_bytes=42,
                sha256="a" * 64,
                kind="source",
            )
        ],
        cost=CostRecord(
            usd=0.01,
            input_tokens=100,
            output_tokens=50,
            source="provider_usage",
        ),
        provenance=Provenance(
            git_sha="deadbeef",
            git_dirty=False,
            python_version="3.12.0",
            platform="test",
            harness_version="0.1.0",
            taxonomy_version="1.0.0",
            pricing_table_version="unset",
            scenario_content_sha256="b" * 64,
            model_ids={"fullstack_developer": "test-model"},
            tier="A",
        ),
    )


def test_trace_json_round_trip() -> None:
    original = _sample_trace()
    dumped = original.model_dump_json()
    restored = Trace.model_validate_json(dumped)
    assert restored == original
    assert restored.spans_of("tool_use")[0].payload["tool"] == "file_writer"
    assert restored.phases() == ["planning"]
    assert restored.errors()[0].span_id == "span_0002"
    assert restored.files("source")[0].path == "src/app.py"


def test_trace_json_schema_emits() -> None:
    schema = Trace.model_json_schema()
    assert "properties" in schema
    assert "spans" in schema["properties"]
    assert schema["properties"]["schema_version"]["default"] == SCHEMA_VERSION
    assert "arm_id" in schema["properties"]


def test_trace_round_trip_with_arm_id_and_context_pressure() -> None:
    """SCHEMA_VERSION 2 fields round-trip when present (harness-alignment 0.3)."""
    original = _sample_trace()
    original = original.model_copy(update={"arm_id": "solo"})
    original.spans[0] = original.spans[0].model_copy(
        update={"type": "phase_end", "payload": {"context_pressure": 0.42}}
    )
    restored = Trace.model_validate_json(original.model_dump_json())
    assert restored.arm_id == "solo"
    assert restored.spans[0].payload["context_pressure"] == 0.42


def test_trace_round_trip_without_new_fields() -> None:
    """Existing traces without arm_id remain valid; field defaults to None."""
    original = _sample_trace()
    dumped = original.model_dump(mode="json")
    dumped.pop("arm_id", None)
    restored = Trace.model_validate(dumped)
    assert restored.arm_id is None


def test_existing_fixture_traces_still_load() -> None:
    """Every committed fixture under evals/fixtures/traces/ still validates."""
    from pathlib import Path

    from evals.trace.schema import migrate_trace_dict

    fixture_dir = Path(__file__).resolve().parents[3] / "evals" / "fixtures" / "traces"
    loaded = 0
    for path in sorted(fixture_dir.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        migrated = migrate_trace_dict(raw)
        trace = Trace.model_validate(migrated)
        assert trace.trace_id
        assert trace.arm_id is None or isinstance(trace.arm_id, str)
        loaded += 1
    assert loaded > 0
