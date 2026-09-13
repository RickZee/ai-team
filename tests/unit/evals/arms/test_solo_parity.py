"""Solo workspace traces through every check; receipt field parity (R2.4 / R2.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.arms.base import ScenarioContract
from evals.arms.solo import SoloArm
from evals.checks.registry import all_checks
from evals.trace.builder import TraceBuilder
from evals.trace.models import Trace

pytestmark = pytest.mark.eval_unit


def _minimal_workspace(root: Path) -> Path:
    ws = root / "solo"
    SoloArm(
        client_factory=lambda: type(
            "C",
            (),
            {
                "sessions": 1,
                "spawned_subagents": 0,
                "guardrails_invoked": False,
                "run": staticmethod(lambda *a, **k: None),
            },
        )()
    ).run(
        ScenarioContract(id="todo-api-beginner", description="brief"),
        ws,
        3.0,
    )
    logs = ws / "logs"
    logs.mkdir(exist_ok=True)
    (logs / "phases.jsonl").write_text(
        '{"timestamp":"2026-09-12T00:00:00Z","phase":"planning","event":"phase_end","status":"ok"}\n',
        encoding="utf-8",
    )
    (logs / "session.json").write_text(
        '{"status":"complete","model_ids":{"*":"configured-default"}}',
        encoding="utf-8",
    )
    (ws / "docs" / "requirements.md").write_text("# todo-api-beginner\n", encoding="utf-8")
    return ws


def test_from_workspace_stamps_arm_id_and_scores(tmp_path: Path) -> None:
    ws = _minimal_workspace(tmp_path)
    trace = TraceBuilder(backend="claude-agent-sdk", tier="A").from_workspace(
        ws, scenario_id="todo-api-beginner"
    )
    assert trace.arm_id == "solo"
    for chk in all_checks(tier="A"):
        result = chk.run(trace)
        assert result.outcome in {"pass", "fail", "not_applicable", "error"}


def test_receipt_fields_match_ai_team(tmp_path: Path) -> None:
    from ai_team.harness.receipt import ReceiptWriter

    solo = _minimal_workspace(tmp_path)
    team = tmp_path / "ai_team"
    team.mkdir()
    (team / "ACCEPTANCE.json").write_text('{"items":[]}', encoding="utf-8")
    writer = ReceiptWriter()
    a = writer.write_from_run(
        output_dir=tmp_path / "out_solo",
        workspace=solo,
        run_id="s",
        backend="claude-agent-sdk",
    )
    b = writer.write_from_run(
        output_dir=tmp_path / "out_team",
        workspace=team,
        run_id="t",
        backend="claude-agent-sdk",
    )
    assert set(a.model_dump()) == set(b.model_dump())


def test_no_claude_settings_in_generated_workspace(tmp_path: Path) -> None:
    ws = _minimal_workspace(tmp_path)
    hits = list(ws.rglob(".claude_settings.json"))
    assert hits == []


def test_from_workspace_tolerates_missing_sessions(tmp_path: Path) -> None:
    ws = _minimal_workspace(tmp_path)
    assert not (ws / "logs" / "sessions.jsonl").is_file()
    trace = TraceBuilder(backend="claude-agent-sdk", tier="A").from_workspace(ws)
    assert isinstance(trace, Trace)
