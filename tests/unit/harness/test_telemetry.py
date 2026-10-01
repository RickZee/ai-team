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
