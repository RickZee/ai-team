"""Integration: TraceBuilder.from_workspace on the miniature fixture (R16.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.store import TraceStore
from evals.trace.builder import TraceBuilder

pytestmark = [pytest.mark.integration, pytest.mark.eval_unit]

_MINI = Path(__file__).resolve().parents[2] / "fixtures" / "mini_workspace"


def test_from_workspace_mini_fixture_integration(tmp_path: Path) -> None:
    assert _MINI.is_dir(), f"missing fixture workspace: {_MINI}"
    store = TraceStore(root=tmp_path / "traces")
    builder = TraceBuilder(
        scenario={"id": "smoke-test"},
        backend="claude-agent-sdk",
        tier="A",
        store=store,
    )
    trace = builder.from_workspace(_MINI, scenario_id="smoke-test")

    assert trace.scenario_id == "smoke-test"
    assert trace.backend == "claude-agent-sdk"
    assert trace.status == "complete"
    assert len(trace.spans) >= 4
    assert "planning" in trace.phases()
    assert "development" in trace.phases()
    assert trace.cost.source in {"sdk_reported", "provider_usage"}
    assert trace.cost.usd is not None
    assert any(a.path.endswith("app.py") for a in trace.artifacts)
    assert any(s.type == "tool_use" for s in trace.spans)
    assert any(s.type == "smoke_probe" for s in trace.spans)
    assert all(s.span_id.startswith("span_") for s in trace.spans)
