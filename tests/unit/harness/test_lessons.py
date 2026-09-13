"""Closed lessons loop: write, dedup, effectiveness, inject."""

from __future__ import annotations

from pathlib import Path

import pytest
from ai_team.config.settings import reload_settings
from ai_team.core.results import ResultsBundle
from ai_team.harness.context import ConstraintLoader
from ai_team.harness.lessons_loop import (
    LessonStore,
    inject_lessons_into_constraints,
    lesson_id_for,
)


def test_write_and_dedup(tmp_path: Path) -> None:
    store = LessonStore(tmp_path / "lessons.jsonl")
    a = store.upsert_from_failure(fm_id="FM-001", evidence_span="span_1")
    b = store.upsert_from_failure(fm_id="FM-001", evidence_span="span_1")
    assert a.lesson_id == b.lesson_id
    assert len(store.all()) == 1
    assert a.lesson_id == lesson_id_for(a.fm_id, a.constraint)


def test_store_failure_does_not_raise(tmp_path: Path) -> None:
    store = LessonStore(tmp_path / "nope" / "lessons.jsonl")
    rec = store.upsert_from_failure(fm_id="FM-006")
    assert rec.fm_id == "FM-006"


def test_effectiveness_and_escalate(tmp_path: Path) -> None:
    store = LessonStore()
    rec = store.upsert_from_failure(fm_id="FM-001")
    rec.recurrence_window = 3
    for _ in range(3):
        store.record_run(["FM-001"])
    assert rec.status == "ineffective"
    store.escalate(rec.lesson_id)
    assert rec.status == "escalated"

    clean = LessonStore()
    clean.upsert_from_failure(fm_id="FM-012")
    clean.all()[0].recurrence_window = 2
    clean.record_run([])
    clean.record_run([])
    assert clean.all()[0].status == "effective"


def test_two_run_inject(tmp_path: Path) -> None:
    store = LessonStore(tmp_path / "lessons.jsonl")
    store.upsert_from_failure(fm_id="FM-001", evidence_span="s1")
    inject_lessons_into_constraints(tmp_path, store)
    loader = ConstraintLoader(tmp_path)
    ids = loader.ids()
    assert any(i.startswith("CST-lesson-") for i in ids)
    second = ConstraintLoader(tmp_path)
    assert any(i.startswith("CST-lesson-") for i in second.ids())
    assert (tmp_path / "docs" / "LESSONS.md").is_file()


def test_lessons_closed_loop_through_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run n writes a lesson; run n+1 loads it — through ResultsBundle, not a direct import."""
    out = tmp_path / "out"
    shared = tmp_path / "shared"
    out.mkdir()
    shared.mkdir()
    monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out))
    monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(shared))
    reload_settings()

    first = ResultsBundle("run-a", workspace_dir=shared)
    first.write_state({"metadata": {"smoke_results": {"ran": True, "success": False}}})
    first.finalize(final_status="error")
    constraints_1 = (shared / "docs" / "CONSTRAINTS.md").read_text(encoding="utf-8")
    assert "CST-lesson-" in constraints_1
    assert (shared / "docs" / "qa_verdicts.jsonl").is_file()

    second = ResultsBundle("run-b", workspace_dir=shared)
    second.init_dirs()
    constraints_2 = (shared / "docs" / "CONSTRAINTS.md").read_text(encoding="utf-8")
    assert "CST-lesson-" in constraints_2
    ids_after = ConstraintLoader(shared).ids()
    assert any(i.startswith("CST-lesson-") for i in ids_after)
