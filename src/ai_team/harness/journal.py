"""Append-only run journal for reconstructable harness events (FM-008).

Replay of a full interactive session (rewind/fork) is **not** supported.
Eval fixture replay + the change receipt remain the durable authorities.
This journal records enough fields to reconstruct tool allow/deny, phase,
spend deltas, and the constraint pin hash for post-hoc inspection.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

JOURNAL_NAME = "journal.jsonl"


class JournalEvent(BaseModel):
    """One reconstructable harness event."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event: str = "tool"
    backend: str | None = None
    phase: str | None = None
    tool: str | None = None
    decision: Literal["allow", "deny", "error", "info"] | None = None
    spend_delta_usd: float | None = None
    constraint_pin_hash: str | None = None
    run_id: str | None = None
    agent_role: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


def journal_path(workspace: Path) -> Path:
    """``workspace/logs/journal.jsonl``."""
    return workspace / "logs" / JOURNAL_NAME


def append_journal_event(workspace: Path, event: JournalEvent | dict[str, Any]) -> Path | None:
    """Append one JSON line. Best-effort; never raises to callers."""
    try:
        row = event if isinstance(event, JournalEvent) else JournalEvent.model_validate(event)
        path = journal_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row.model_dump(mode="json"), default=str) + "\n")
        return path
    except (OSError, ValueError) as exc:
        logger.debug("journal_append_skipped", error=str(exc))
        return None


def constraint_pin_hash_for(workspace: Path) -> str | None:
    """SHA-256 of pinned CONSTRAINTS.md text, or None if empty/missing."""
    try:
        from ai_team.harness.context import ConstraintLoader

        loader = ConstraintLoader(workspace)
        if not loader.path.is_file() or not loader.load():
            return None
        return loader.sha256()
    except (OSError, ValueError, RuntimeError):
        return None
