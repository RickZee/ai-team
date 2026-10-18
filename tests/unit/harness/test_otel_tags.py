"""The run-id helper tags a framework's root span (otel-observability R4.2)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from ai_team.harness.otel_tags import run_attributes, tag_root_span


class _FakeTracer:
    def __init__(self) -> None:
        self.started: list[tuple[str, dict[str, Any]]] = []

    @contextmanager
    def start_as_current_span(self, name: str, attributes: dict[str, Any] | None = None):
        self.started.append((name, dict(attributes or {})))
        yield name


def test_root_span_carries_run_attributes() -> None:
    tracer = _FakeTracer()
    with tag_root_span(tracer, run_id="run-1", backend="strands") as span:
        assert span == "ai_team.run"
    name, attrs = tracer.started[0]
    assert name == "ai_team.run"
    assert attrs == run_attributes(run_id="run-1", backend="strands")
    assert attrs["ai_team.source"] == "framework"
    assert attrs["openinference.project.name"] == "ai-team"


def test_no_tracer_is_a_no_op() -> None:
    with tag_root_span(None, run_id="run-1", backend="strands") as span:
        assert span is None
