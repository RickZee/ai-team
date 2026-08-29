"""Closed lessons loop: structured records, dedup, effectiveness (R18)."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

_WS_RE = re.compile(r"\s+")


class LessonRecord(BaseModel):
    """One structured lesson written on smoke/check failure."""

    lesson_id: str
    fm_id: str
    constraint: str
    evidence_span: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ttl_runs: int = 20
    recurrence_window: int = 5
    recurrences: int = 0
    runs_seen: int = 0
    status: Literal["active", "effective", "ineffective", "escalated"] = "active"


def normalize_constraint(text: str) -> str:
    """Lowercase collapsed whitespace for dedup."""
    return _WS_RE.sub(" ", (text or "").strip().lower())


def lesson_id_for(fm_id: str, constraint: str) -> str:
    """Stable id from fm_id + normalized constraint."""
    key = f"{fm_id}|{normalize_constraint(constraint)}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"L-{fm_id}-{digest}"


def template_constraint(fm_id: str, evidence: str | None = None) -> str:
    """Deterministic one-sentence constraint. No LLM."""
    evidence_bit = f" Evidence: {evidence}." if evidence else ""
    return (
        f"MUST prevent {fm_id} from recurring.{evidence_bit} "
        "Use the ToolBus; do not emit code only as markdown fences."
    )


class LessonStore:
    """In-memory + JSONL store used when SQLite is unavailable or for tests."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._by_id: dict[str, LessonRecord] = {}
        if path and path.is_file():
            self._load()

    def _load(self) -> None:
        assert self.path is not None
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = LessonRecord.model_validate_json(line)
            self._by_id[rec.lesson_id] = rec

    def _persist(self) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            lines = [r.model_dump_json() for r in self._by_id.values()]
            self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        except OSError as exc:
            logger.warning("lesson_store_persist_failed", error=str(exc))

    def upsert_from_failure(
        self,
        *,
        fm_id: str,
        evidence_span: str | None = None,
        constraint: str | None = None,
    ) -> LessonRecord:
        """Write or return existing lesson. Never raises."""
        try:
            text = constraint or template_constraint(fm_id, evidence_span)
            lid = lesson_id_for(fm_id, text)
            existing = self._by_id.get(lid)
            if existing:
                return existing
            rec = LessonRecord(
                lesson_id=lid, fm_id=fm_id, constraint=text, evidence_span=evidence_span
            )
            self._by_id[lid] = rec
            self._persist()
            return rec
        except Exception as exc:  # noqa: BLE001 — lessons must never abort a run
            logger.warning("lesson_upsert_failed", error=str(exc))
            return LessonRecord(
                lesson_id="L-error",
                fm_id=fm_id,
                constraint=template_constraint(fm_id),
                status="active",
            )

    def record_run(self, failure_ids: list[str]) -> None:
        """Tick recurrence window. Mark effective / ineffective / escalate."""
        failed = set(failure_ids)
        for rec in self._by_id.values():
            if rec.status in {"effective", "escalated"}:
                continue
            rec.runs_seen += 1
            if rec.fm_id in failed:
                rec.recurrences += 1
            if rec.runs_seen >= rec.recurrence_window:
                if rec.recurrences == 0:
                    rec.status = "effective"
                elif rec.status != "escalated":
                    rec.status = "ineffective"
        self._persist()

    def escalate(self, lesson_id: str) -> LessonRecord | None:
        rec = self._by_id.get(lesson_id)
        if rec is None:
            return None
        rec.status = "escalated"
        rec.constraint = (
            rec.constraint + " ESCALATED: constraint was too soft or targeted the wrong layer."
        )
        self._persist()
        return rec

    def active(self) -> list[LessonRecord]:
        return [r for r in self._by_id.values() if r.status in {"active", "ineffective"}]

    def all(self) -> list[LessonRecord]:
        return list(self._by_id.values())


def inject_lessons_into_constraints(workspace: Path, store: LessonStore) -> None:
    """Append active lessons as pinned CST-lesson-* items."""
    from ai_team.harness.context import ConstraintItem, ConstraintLoader, write_lessons_md

    loader = ConstraintLoader(workspace)
    loader.ensure()
    for rec in store.active():
        loader.append(
            ConstraintItem(
                id=f"CST-lesson-{rec.lesson_id}",
                text=rec.constraint,
                source="lesson",
                pinned=True,
            )
        )
    write_lessons_md(workspace, [r.model_dump(mode="json") for r in store.all()])
