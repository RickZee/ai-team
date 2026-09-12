"""Unit tests for harness journal.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

from ai_team.harness.journal import (
    JournalEvent,
    append_journal_event,
    constraint_pin_hash_for,
    journal_path,
)


class TestJournal:
    def test_append_writes_reconstructable_fields(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        path = append_journal_event(
            ws,
            JournalEvent(
                event="tool",
                backend="crewai",
                phase="development",
                tool="file_writer",
                decision="allow",
                spend_delta_usd=0.01,
                constraint_pin_hash="abc123",
                run_id="run-1",
                agent_role="backend_developer",
            ),
        )
        assert path == journal_path(ws)
        assert path is not None
        row = json.loads(path.read_text(encoding="utf-8").strip())
        assert row["backend"] == "crewai"
        assert row["phase"] == "development"
        assert row["tool"] == "file_writer"
        assert row["decision"] == "allow"
        assert row["spend_delta_usd"] == 0.01
        assert row["constraint_pin_hash"] == "abc123"
        assert row["run_id"] == "run-1"

    def test_constraint_pin_hash_none_without_file(self, tmp_path: Path) -> None:
        assert constraint_pin_hash_for(tmp_path / "empty") is None
