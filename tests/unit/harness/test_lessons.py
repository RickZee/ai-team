"""Closed lessons loop: write, dedup, effectiveness, inject."""

from __future__ import annotations

from pathlib import Path

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
