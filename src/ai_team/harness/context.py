"""Pinned constraints, STATE.md facts, and LESSONS.md — harness-owned, not LLM-owned.

``CONSTRAINTS.md`` is never summarized. ``STATE.md`` is last-N phase facts.
``LESSONS.md`` is generated from the lessons store.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

CONSTRAINTS_NAME = "CONSTRAINTS.md"
STATE_NAME = "STATE.md"
LESSONS_NAME = "LESSONS.md"
DEFAULT_STATE_PHASES = 5

_HEADING_RE = re.compile(r"^##\s+(CST-\S+)\s*$", re.MULTILINE)


class ConstraintItem(BaseModel):
    """One pinned constraint."""

    id: str
    text: str
    source: Literal["human", "harness", "lesson"] = "human"
    pinned: bool = True


class PhaseFacts(BaseModel):
    """Structured facts for one completed phase. Not prose."""

    phase: str
    files_written: list[str] = Field(default_factory=list)
    tests: dict[str, Any] = Field(default_factory=dict)
    smoke: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)
    ended_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def _docs_dir(workspace: Path) -> Path:
    docs = workspace / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    return docs


def _parse_constraints(markdown: str) -> list[ConstraintItem]:
    items: list[ConstraintItem] = []
    parts = _HEADING_RE.split(markdown)
    # split keeps capture groups: [pre, id1, body1, id2, body2, ...]
    if len(parts) < 2:
        return items
    for i in range(1, len(parts), 2):
        cid = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        source: Literal["human", "harness", "lesson"] = "human"
        if cid.startswith("CST-lesson-"):
            source = "lesson"
        elif cid.startswith("CST-canary") or cid.startswith("CST-harness"):
            source = "harness"
        items.append(ConstraintItem(id=cid, text=body, source=source, pinned=True))
    return items


def _render_constraints(items: list[ConstraintItem]) -> str:
    lines = [
        "# Constraints",
        "",
        "Pinned. The summarizer is not allowed to drop or rewrite these.",
        "",
    ]
    for item in items:
        lines.append(f"## {item.id}")
        lines.append("")
        lines.append(item.text.strip() or "(empty)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


class ConstraintLoader:
    """Load, append, and inject ``docs/CONSTRAINTS.md``."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.path = _docs_dir(self.workspace) / CONSTRAINTS_NAME

    def ensure(self, *, canary: str | None = None) -> list[ConstraintItem]:
        """Create the file from a template if missing. Optionally add a canary."""
        if not self.path.is_file():
            items: list[ConstraintItem] = []
            if canary or os.environ.get("AI_TEAM_CONSTRAINT_CANARY"):
                text = canary or os.environ["AI_TEAM_CONSTRAINT_CANARY"]
                items.append(
                    ConstraintItem(id="CST-canary", text=text, source="harness", pinned=True)
                )
            self.path.write_text(_render_constraints(items), encoding="utf-8")
            logger.info("constraints_created", path=str(self.path), n=len(items))
        return self.load()

    def load(self) -> list[ConstraintItem]:
        """Parse the file. Empty list if missing."""
        if not self.path.is_file():
            return []
        return _parse_constraints(self.path.read_text(encoding="utf-8"))

    def append(self, item: ConstraintItem) -> None:
        """Append a constraint. Dedup by id."""
        items = self.ensure()
        if any(existing.id == item.id for existing in items):
            items = [existing if existing.id != item.id else item for existing in items]
        else:
            items.append(item)
        self.path.write_text(_render_constraints(items), encoding="utf-8")

    def pinned_text(self) -> str:
        """Full file contents. Compaction must not rewrite this string."""
        self.ensure()
        return self.path.read_text(encoding="utf-8")

    def ids(self) -> list[str]:
        """Constraint ids in file order."""
        return [c.id for c in self.load()]

    def sha256(self) -> str:
        """Hash of pinned text for traces."""
        return hashlib.sha256(self.pinned_text().encode("utf-8")).hexdigest()

    def inject_block(self) -> str:
        """Prompt prefix: full constraints, labelled as pinned.

        Empty when the file is missing or has no items so agent YAML loaders
        do not rewrite every backstory in tests.
        """
        if not self.path.is_file():
            return ""
        items = self.load()
        if not items:
            return ""
        body = self.path.read_text(encoding="utf-8").strip()
        return "PINNED CONSTRAINTS (do not summarize, drop, or contradict):\n\n" + body + "\n"

    def phase_start_payload(self) -> dict[str, Any]:
        """Ids + hash for ``phase_start`` / ``context_inject`` spans."""
        items = self.load()
        return {
            "constraint_ids": [c.id for c in items],
            "constraint_sha256": self.sha256() if self.path.is_file() else "",
        }


class StateWriter:
    """Deterministic ``docs/STATE.md`` writer. No LLM."""

    def __init__(self, workspace: Path, *, keep: int = DEFAULT_STATE_PHASES) -> None:
        self.workspace = workspace.resolve()
        self.path = _docs_dir(self.workspace) / STATE_NAME
        self.keep = keep

    def load_phases(self) -> list[PhaseFacts]:
        """Parse the JSON facts fence from STATE.md."""
        if not self.path.is_file():
            return []
        text = self.path.read_text(encoding="utf-8")
        m = re.search(r"```json\n(.*?)```", text, re.DOTALL)
        if not m:
            return []
        try:
            raw = json.loads(m.group(1))
        except json.JSONDecodeError:
            return []
        if not isinstance(raw, list):
            return []
        out: list[PhaseFacts] = []
        for row in raw:
            if isinstance(row, dict):
                out.append(PhaseFacts.model_validate(row))
        return out

    def write(self, facts: PhaseFacts) -> None:
        """Append *facts* and keep only the last N phases."""
        phases = self.load_phases()
        phases.append(facts)
        phases = phases[-self.keep :]
        payload = json.dumps([p.model_dump(mode="json") for p in phases], indent=2)
        bullets = "\n".join(
            f"- **{p.phase}**: files={len(p.files_written)} errors={len(p.errors)}" for p in phases
        )
        text = (
            "# Run state\n\n"
            "Facts only. Last N phases. Written by the harness, not the model.\n\n"
            f"{bullets}\n\n"
            f"```json\n{payload}\n```\n"
        )
        self.path.write_text(text, encoding="utf-8")
        logger.info("state_md_written", phase=facts.phase, kept=len(phases))


def write_lessons_md(workspace: Path, lessons: list[dict[str, Any]]) -> Path:
    """Render ``docs/LESSONS.md`` from structured lesson dicts."""
    path = _docs_dir(workspace) / LESSONS_NAME
    lines = [
        "# Lessons",
        "",
        "| id | fm_id | status | constraint |",
        "| --- | --- | --- | --- |",
    ]
    for row in lessons:
        cid = str(row.get("lesson_id") or "")
        fm = str(row.get("fm_id") or "")
        status = str(row.get("status") or "active")
        constraint = str(row.get("constraint") or "").replace("|", "\\|")[:200]
        lines.append(f"| `{cid}` | {fm} | {status} | {constraint} |")
    if len(lessons) == 0:
        lines.append("| — | — | — | (none yet) |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def dummy_summarize(other_context: str, pinned: str) -> str:
    """Compaction stand-in: drop *other_context*, keep *pinned* verbatim.

    Proves the pin survives a summarizer that empties everything else.
    """
    _ = other_context
    return pinned
