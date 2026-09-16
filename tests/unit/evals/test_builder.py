"""Tests for TraceBuilder.from_workspace (task 1.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.store import TraceStore
from evals.trace.builder import TraceBuilder

pytestmark = pytest.mark.eval_unit

_MINI = Path(__file__).resolve().parents[2] / "fixtures" / "mini_workspace"


def test_from_workspace_mini_fixture(tmp_path: Path) -> None:
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


def test_from_workspace_warns_without_audit(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "logs").mkdir(parents=True)
    (ws / "logs" / "phases.jsonl").write_text(
        '{"phase":"planning","status":"completed","timestamp":"2026-08-01T12:00:00+00:00"}\n',
        encoding="utf-8",
    )
    store = TraceStore(root=tmp_path / "traces")
    builder = TraceBuilder(backend="crewai", store=store)
    trace = builder.from_workspace(ws, scenario_id="x", backend="crewai")
    assert any(
        w == "no audit log for backend=crewai; tool-level checks skipped" for w in trace.warnings
    )


def _run_dir(tmp_path: Path, run: dict | None = None, state: dict | None = None) -> Path:
    import json

    rd = tmp_path / "runs" / "r1"
    (rd / "logs").mkdir(parents=True)
    if run is not None:
        (rd / "run.json").write_text(json.dumps(run), encoding="utf-8")
    if state is not None:
        (rd / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return rd


def test_backfill_reads_backend_status_and_clock_from_run_record(tmp_path: Path) -> None:
    """Regression: backfill once stamped every run ``crewai / failed`` at build time."""
    rd = _run_dir(
        tmp_path,
        run={
            "backend": "langgraph",
            "started_at": "2026-09-13T18:26:50Z",
            "completed_at": "2026-09-13T18:53:26+00:00",
            "extra": {"final_status": "complete"},
        },
    )
    trace = TraceBuilder(backend=None, store=TraceStore(root=tmp_path / "t")).from_workspace(rd)
    assert trace.backend == "langgraph"
    assert trace.status == "complete"
    assert trace.started_at.isoformat() == "2026-09-13T18:26:50+00:00"
    assert trace.ended_at is not None and trace.ended_at.minute == 53


def test_backfill_unrecorded_backend_is_unknown_not_crewai(tmp_path: Path) -> None:
    rd = _run_dir(tmp_path, run={"started_at": None, "completed_at": None})
    trace = TraceBuilder(backend=None, store=TraceStore(root=tmp_path / "t")).from_workspace(rd)
    assert trace.backend == "unknown"
    assert trace.status == "failed"
    assert any("backend not recorded" in w for w in trace.warnings)
    assert any("no final status recorded" in w for w in trace.warnings)


def test_backfill_status_falls_back_to_state_json_phase(tmp_path: Path) -> None:
    rd = _run_dir(
        tmp_path,
        run={"backend": "langgraph", "completed_at": None},
        state={"state": {"current_phase": "complete"}},
    )
    trace = TraceBuilder(backend=None, store=TraceStore(root=tmp_path / "t")).from_workspace(rd)
    assert trace.status == "complete"


def test_explicit_backend_still_wins_over_run_record(tmp_path: Path) -> None:
    rd = _run_dir(tmp_path, run={"backend": "langgraph"})
    trace = TraceBuilder(backend="crewai", store=TraceStore(root=tmp_path / "t")).from_workspace(rd)
    assert trace.backend == "crewai"
