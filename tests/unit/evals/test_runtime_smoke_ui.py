"""CHK-runtime-smoke-present requires UI smoke on UI-bearing scenarios (R13.8)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from evals.checks.registry import get_check
from evals.provenance import Provenance
from evals.trace.models import CostRecord, Span, Trace

pytestmark = pytest.mark.eval_unit


def _trace(*, ui: bool, ui_smoke_ok: bool = False) -> Trace:
    now = datetime.now(UTC)
    probes = [
        Span(
            span_id="http",
            type="smoke_probe",
            t_start=now,
            payload={"success": True, "ran": True, "kind": "http"},
        )
    ]
    if ui_smoke_ok:
        probes.append(
            Span(
                span_id="ui",
                type="smoke_probe",
                t_start=now,
                payload={"success": True, "ran": True, "kind": "ui"},
            )
        )
    raw = {"ui": {"base_url": "http://127.0.0.1:5000"}} if ui else {}
    return Trace(
        trace_id="t",
        scenario_id="todo-api-beginner" if ui else "hello-world-smoke",
        backend="claude-agent-sdk",
        status="complete",
        started_at=now,
        ended_at=now,
        spans=probes,
        artifacts=[],
        cost=CostRecord(usd=0.0, input_tokens=0, output_tokens=0, source="unknown"),
        provenance=Provenance(
            git_sha="x",
            git_dirty=False,
            python_version="3.12",
            platform="test",
            harness_version="0",
            taxonomy_version="1.2.0",
            pricing_table_version="unset",
        ),
        raw_result=raw,
    )


def test_http_only_fails_ui_scenario_passes_non_ui() -> None:
    chk = get_check("CHK-runtime-smoke-present")
    ui_only_http = chk.run(_trace(ui=True, ui_smoke_ok=False))
    assert ui_only_http.outcome == "fail"
    non_ui = chk.run(_trace(ui=False))
    assert non_ui.outcome == "pass"
    ui_ok = chk.run(_trace(ui=True, ui_smoke_ok=True))
    assert ui_ok.outcome == "pass"
