"""Tests for TraceBuilder.from_workspace (task 1.4)."""

from __future__ import annotations

import json
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


class TestAgentWorkspaceTelemetry:
    """A run writes two trees; the builder must read both.

    ``output/runs/<id>/`` holds the record and ``logs/costs.jsonl``. ``workspace/<id>/`` —
    where the agents actually worked — holds ``logs/audit.jsonl`` (every tool call) and
    ``docs/qa_verdicts.jsonl``. Reading only the first tree gave a 385-trace corpus containing
    0 tool spans and 0 phase spans: every span in it was a cost row (2026-09-18). Pointing the
    reader at both recovered 1171 tool_use, 1171 tool_result and 144 qa_verdict spans, and took
    the traces with 20+ spans from 3 to 32.

    Week 3 of the course teaches exactly this shape — the writer and the reader disagreeing
    about where a run lives — one level up, at the corpus root. This is the same bug inside
    each run, and ``run.json`` recorded the path the whole time.
    """

    @staticmethod
    def _run_with_sibling_workspace(tmp_path: Path, *, record_abs_path: bool) -> Path:
        repo = tmp_path / "repo"
        run_dir = repo / "output" / "runs" / "2026-09-18_run_01"
        agent_ws = repo / "workspace" / "2026-09-18_run_01"
        (run_dir / "logs").mkdir(parents=True)
        (agent_ws / "logs").mkdir(parents=True)
        (agent_ws / "docs").mkdir(parents=True)

        record: dict[str, object] = {
            "project_id": "2026-09-18_run_01",
            "backend": "langgraph",
            "started_at": "2026-09-18T22:49:14Z",
            "completed_at": "2026-09-18T22:51:30Z",
        }
        if record_abs_path:
            record["workspace_dir"] = str(agent_ws)
        (run_dir / "run.json").write_text(json.dumps(record), encoding="utf-8")

        # the one telemetry file that lands beside the record
        (run_dir / "logs" / "costs.jsonl").write_text(
            json.dumps({"kind": "run_total", "spent_usd": 0.0027, "calls": 12}) + "\n",
            encoding="utf-8",
        )
        # the tool log, in the tree the builder used to ignore
        (agent_ws / "logs" / "audit.jsonl").write_text(
            "\n".join(
                json.dumps(
                    {
                        "type": "tool_use",
                        "timestamp": f"2026-09-18T22:50:1{i}+00:00",
                        "tool": "write_file",
                        "tool_name": "write_file",
                        "kind": "write",
                        "risk_class": "write",
                    }
                )
                for i in range(4)
            )
            + "\n",
            encoding="utf-8",
        )
        return run_dir

    def _build(self, run_dir: Path, tmp_path: Path):
        store = TraceStore(root=tmp_path / "traces")
        return TraceBuilder(backend="langgraph", store=store).from_workspace(
            run_dir, scenario_id="smoke-test", backend="langgraph"
        )

    def test_tool_spans_come_from_the_agent_workspace(self, tmp_path: Path) -> None:
        run_dir = self._run_with_sibling_workspace(tmp_path, record_abs_path=True)
        trace = self._build(run_dir, tmp_path)

        kinds = {s.type for s in trace.spans}
        assert "tool_use" in kinds, f"only found {kinds}; the audit log was not read"
        assert len([s for s in trace.spans if s.type == "tool_use"]) == 4

    def test_it_works_without_the_recorded_path(self, tmp_path: Path) -> None:
        """``workspace_dir`` is absolute and host-specific, so the layout must also work."""
        run_dir = self._run_with_sibling_workspace(tmp_path, record_abs_path=False)
        trace = self._build(run_dir, tmp_path)
        assert any(s.type == "tool_use" for s in trace.spans)

    def test_the_trace_says_where_it_read_from(self, tmp_path: Path) -> None:
        run_dir = self._run_with_sibling_workspace(tmp_path, record_abs_path=True)
        trace = self._build(run_dir, tmp_path)
        assert any("agent workspace" in w for w in trace.warnings), trace.warnings

    def test_a_file_in_the_run_directory_still_wins(self, tmp_path: Path) -> None:
        run_dir = self._run_with_sibling_workspace(tmp_path, record_abs_path=True)
        (run_dir / "logs" / "audit.jsonl").write_text(
            json.dumps(
                {
                    "type": "tool_use",
                    "timestamp": "2026-09-18T22:50:00+00:00",
                    "tool": "read_file",
                    "tool_name": "read_file",
                    "kind": "read",
                    "risk_class": "read",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        trace = self._build(run_dir, tmp_path)
        uses = [s for s in trace.spans if s.type == "tool_use"]
        assert len(uses) == 1, "the run directory's own log must take precedence"
        assert not any("agent workspace" in w for w in trace.warnings)

    def test_no_sibling_workspace_is_not_an_error(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "solo" / "output" / "runs" / "r1"
        (run_dir / "logs").mkdir(parents=True)
        (run_dir / "run.json").write_text(
            json.dumps({"project_id": "r1", "backend": "langgraph"}), encoding="utf-8"
        )
        trace = self._build(run_dir, tmp_path)
        assert trace.spans == [] or all(s.type != "tool_use" for s in trace.spans)
