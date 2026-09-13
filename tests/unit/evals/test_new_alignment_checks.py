"""Negative controls and helpers for harness-alignment Phase 2 checks."""

from __future__ import annotations

from pathlib import Path

import pytest
from ai_team.harness.context_pressure import context_pressure, pressure_from_usage
from ai_team.harness.qa_verdicts import (
    QaIssue,
    QaVerdict,
    VerifierIdentity,
    append_verdict,
    load_verdicts,
    prompt_hash,
)

from evals.checks.registry import get_check
from evals.trace.builder import TraceBuilder
from tests.unit.evals.trace_fixtures import _span, base_trace

pytestmark = pytest.mark.eval_unit


def test_context_pressure_none_when_unknown() -> None:
    assert context_pressure(None, 100_000) is None
    assert context_pressure(100, None) is None
    assert context_pressure(50, 100) == 0.5
    assert context_pressure(200, 100) == 1.0
    assert pressure_from_usage(None, window_tokens=1000) is None
    assert (
        pressure_from_usage({"input_tokens": 100, "output_tokens": 50}, window_tokens=1000) == 0.15
    )


def test_premature_negative_controls_do_not_fire() -> None:
    chk = get_check("CHK-premature-termination")
    assert chk is not None
    base_spans_ok = [
        _span(
            0, "phase_end", phase="development", payload={"status": "ok", "context_pressure": 0.9}
        )
    ]
    raw = {"acceptance_unsatisfied": 1}

    spend = base_trace(
        check_id="CHK-premature-termination",
        outcome="pass",
        spans=base_spans_ok + [_span(1, "spend_event", payload={"usd": 3.0}, t_offset_s=1)],
        raw_result=raw,
        status="complete",
    )
    assert chk.run(spend).outcome == "pass"

    watchdog = base_trace(
        check_id="CHK-premature-termination",
        outcome="pass",
        spans=[
            _span(
                0,
                "phase_end",
                phase="development",
                payload={"status": "ok", "context_pressure": 0.9, "watchdog": True},
            )
        ],
        raw_result=raw,
        status="killed",
    )
    assert chk.run(watchdog).outcome == "pass"

    err = base_trace(
        check_id="CHK-premature-termination",
        outcome="pass",
        spans=base_spans_ok + [_span(1, "error", payload={"message": "boom"}, t_offset_s=1)],
        raw_result=raw,
        status="complete",
    )
    assert chk.run(err).outcome == "pass"

    max_turns = base_trace(
        check_id="CHK-premature-termination",
        outcome="pass",
        spans=[
            _span(
                0,
                "phase_end",
                phase="development",
                payload={"status": "ok", "context_pressure": 0.9, "max_turns": True},
            )
        ],
        raw_result=raw,
        status="complete",
    )
    assert chk.run(max_turns).outcome == "pass"


def test_qa_verdicts_round_trip_and_absent_ok(tmp_path: Path) -> None:
    assert load_verdicts(tmp_path) == []
    v = QaVerdict(
        item_id="abc",
        verdict="reject",
        issues=[QaIssue(description="missing auth", severity="major")],
        evidence=["docs/qa.md"],
        qa_prompt_hash=prompt_hash("qa v1"),
        identity=VerifierIdentity(agent_role="qa_engineer", session_id="s1"),
    )
    append_verdict(tmp_path, v)
    loaded = load_verdicts(tmp_path)
    assert loaded[0].qa_prompt_hash == prompt_hash("qa v1")
    (tmp_path / "logs").mkdir(exist_ok=True)
    trace = TraceBuilder(backend="crewai", tier="A").from_workspace(tmp_path)
    assert any(s.type == "qa_verdict" for s in trace.spans)
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "logs").mkdir()
    t2 = TraceBuilder(backend="crewai", tier="A").from_workspace(empty)
    assert not any(s.type == "qa_verdict" for s in t2.spans)


def test_token_tracker_pressure_none_without_window() -> None:
    from unittest.mock import MagicMock

    from ai_team.config.token_tracker import TokenTracker

    settings = MagicMock()
    settings.max_cost_per_run = 10.0
    tracker = TokenTracker(settings)
    tracker.record("qa_engineer", 100, 20, 0.01)
    assert tracker.context_pressure(None) is None
    assert tracker.context_pressure(200) == 0.6


def test_emit_phase_end_writes_none_without_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai_team.harness.context_pressure import emit_phase_end

    monkeypatch.delenv("AI_TEAM_CONTEXT_WINDOW_TOKENS", raising=False)
    emit_phase_end(tmp_path, "planning", used_tokens=100, status="ok")
    import json

    row = json.loads((tmp_path / "logs" / "phases.jsonl").read_text(encoding="utf-8"))
    assert row["context_pressure"] is None
    monkeypatch.setenv("AI_TEAM_CONTEXT_WINDOW_TOKENS", "200")
    emit_phase_end(tmp_path, "planning", used_tokens=100, status="ok")
    lines = (tmp_path / "logs" / "phases.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(lines[-1])["context_pressure"] == 0.5
