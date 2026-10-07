"""Harness telemetry: provenance is stamped by the module, and zero spend is a row."""

from __future__ import annotations

import json
from pathlib import Path

from ai_team.harness.telemetry import TelemetryWriter


def test_run_total_records_zero_when_spend_is_missing(tmp_path: Path) -> None:
    TelemetryWriter(tmp_path).run_total(None)
    row = json.loads((tmp_path / "logs" / "costs.jsonl").read_text(encoding="utf-8"))
    assert row["kind"] == "run_total"
    assert row["spent_usd"] == 0.0
    assert row["calls"] == 0
    assert row["writer"] == "harness"


def test_caller_cannot_forge_writer(tmp_path: Path) -> None:
    TelemetryWriter(tmp_path).run_total({"spent_usd": 0.01, "calls": 1, "writer": "agent"})
    row = json.loads((tmp_path / "logs" / "costs.jsonl").read_text(encoding="utf-8"))
    assert row["writer"] == "harness"
    assert row["spent_usd"] == 0.01


def test_write_failure_does_not_raise(tmp_path: Path) -> None:
    blocked = tmp_path / "logs"
    blocked.write_text("not a directory", encoding="utf-8")
    TelemetryWriter(tmp_path).run_total({"spent_usd": 1.0, "calls": 1})


def test_phases_from_history_stamps_harness(tmp_path: Path) -> None:
    TelemetryWriter(tmp_path).phases_from_history(
        [{"phase": "planning", "status": "complete"}, "skip", {"phase": ""}],
        run_id="run-1",
        backend="langgraph",
    )
    rows = [
        json.loads(line)
        for line in (tmp_path / "logs" / "phases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["status"] for row in rows] == ["phase_start", "phase_end"]
    assert rows[0]["phase"] == "planning"
    assert rows[0]["writer"] == "harness"
    assert rows[1]["end_status"] == "complete"
    assert rows[1]["context_pressure"] is None


def test_orchestrator_prompt_does_not_ask_for_phase_log() -> None:
    from ai_team.backends.claude_agent_sdk_backend.agents.prompts import orchestrator_prompt

    text = orchestrator_prompt(
        profile_name="full",
        agent_list="architect",
        phase_list="planning",
        max_retries=3,
    )
    assert "phases.jsonl" not in text
