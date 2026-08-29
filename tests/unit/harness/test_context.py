"""Pinned constraints, STATE.md, compaction pin survival."""

from __future__ import annotations

from pathlib import Path

import pytest
from ai_team.harness.context import (
    ConstraintItem,
    ConstraintLoader,
    PhaseFacts,
    StateWriter,
    dummy_summarize,
    write_lessons_md,
)


def test_constraints_round_trip(tmp_path: Path) -> None:
    loader = ConstraintLoader(tmp_path)
    loader.append(ConstraintItem(id="CST-canary", text="must keep canary-xyz", source="harness"))
    loader.append(ConstraintItem(id="CST-human-1", text="no secrets in src/", source="human"))
    again = ConstraintLoader(tmp_path)
    ids = again.ids()
    assert "CST-canary" in ids
    assert "CST-human-1" in ids
    text = again.pinned_text()
    assert "must keep canary-xyz" in text
    payload = again.phase_start_payload()
    assert "CST-canary" in payload["constraint_ids"]
    assert len(payload["constraint_sha256"]) == 64


def test_state_keeps_last_n(tmp_path: Path) -> None:
    writer = StateWriter(tmp_path, keep=3)
    for i in range(5):
        writer.write(PhaseFacts(phase=f"p{i}", files_written=[f"f{i}"]))
    phases = writer.load_phases()
    assert [p.phase for p in phases] == ["p2", "p3", "p4"]


def test_dummy_summarizer_keeps_pin(tmp_path: Path) -> None:
    loader = ConstraintLoader(tmp_path)
    loader.append(ConstraintItem(id="CST-canary", text="keep-me", source="harness"))
    pinned = loader.pinned_text()
    out = dummy_summarize("lots of other context that should vanish", pinned)
    assert out == pinned
    assert "keep-me" in out


def test_inject_block_empty_when_missing(tmp_path: Path) -> None:
    assert ConstraintLoader(tmp_path).inject_block() == ""


def test_lessons_md(tmp_path: Path) -> None:
    path = write_lessons_md(tmp_path, [{"lesson_id": "L-1", "fm_id": "FM-001", "status": "active"}])
    assert path.is_file()
    assert "L-1" in path.read_text(encoding="utf-8")


def test_langgraph_prompt_includes_canary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(tmp_path))
    from ai_team.config.settings import reload_settings

    reload_settings()
    ConstraintLoader(tmp_path).append(
        ConstraintItem(id="CST-canary", text="canary-token-42", source="harness")
    )
    from ai_team.backends.langgraph_backend.agents.prompts import build_system_prompt

    prompt = build_system_prompt("architect")
    assert "canary-token-42" in prompt
    assert "PINNED CONSTRAINTS" in prompt
