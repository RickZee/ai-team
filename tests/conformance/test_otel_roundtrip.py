"""Every backend's thin slice exports to OTLP and reads back as the same trace (otel R3.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.store import TraceStore
from evals.trace.builder import TraceBuilder
from evals.trace.otel_export import ExportOptions, export_requests, to_jsonl
from evals.trace.otel_import import import_otlp, kind_counts
from tests.conformance.conftest import BACKENDS

pytestmark = pytest.mark.parametrize("thin_run", BACKENDS, indirect=True)


def _signature(spans) -> list[tuple]:
    return sorted((s.type, s.agent_role or "", s.phase or "", s.t_start) for s in spans)


def test_export_then_import_gives_back_the_trace(thin_run, tmp_path: Path) -> None:
    backend = thin_run.backend_name if thin_run.backend_name != "fake-remote" else None
    run_dir = Path(str(thin_run.raw["output_dir"]))
    trace = TraceBuilder(
        backend=backend, scenario={"id": "thin-slice"}, store=TraceStore(root=tmp_path / "t")
    ).from_workspace(run_dir)
    assert trace.spans, "thin slice produced no spans"

    path = tmp_path / "otel.harness.jsonl"
    body = to_jsonl(export_requests(trace, ExportOptions(run_id=run_dir.name)))
    path.write_text(body, encoding="utf-8")
    back = import_otlp(path)

    assert kind_counts(back) == kind_counts(trace.spans)
    assert _signature(back) == _signature(trace.spans)
    assert body == to_jsonl(export_requests(trace, ExportOptions(run_id=run_dir.name)))
