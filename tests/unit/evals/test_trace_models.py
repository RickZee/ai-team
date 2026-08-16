"""Round-trip and schema tests for Trace models (task 1.1)."""

from __future__ import annotations

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
