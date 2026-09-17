"""Draft-then-commit staging for ToolBus write tools.

Live workspace paths are untouched until :func:`commit_draft`. Draft bytes live
under ``workspace/.harness/drafts/<draft_id>``.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

DRAFTS_SUBDIR = Path(".harness") / "drafts"
MANIFEST_NAME = "manifest.json"


class DraftRecord(BaseModel):
    """One staged write waiting for commit."""

    draft_id: str
    intended_path: str
    sha256: str
    created_at: datetime
    agent_role: str | None = None
    phase: str | None = None


class CommitResult(BaseModel):
    """Outcome of promoting one or more drafts."""

    ok: bool
    committed: list[str] = Field(default_factory=list)
    rejected: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def _drafts_root(workspace: Path) -> Path:
    return workspace.resolve() / DRAFTS_SUBDIR


def _safe_intended_path(workspace: Path, intended_path: str) -> Path:
    """Resolve *intended_path* under *workspace*; reject traversal and abs paths."""
    raw = intended_path.strip()
    if not raw or ".." in Path(raw).parts or Path(raw).is_absolute():
        raise ValueError(f"Invalid draft path: {intended_path!r}")
    if Path(raw).parts[0] == ".harness":
        # Agents that see a draft ref sometimes try to write *to* it; harness files are
        # never an agent's target.
        raise ValueError(f"Invalid draft path (harness area): {intended_path!r}")
    dest = (workspace.resolve() / raw).resolve()
    try:
        dest.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError(f"Draft path escapes workspace: {intended_path}") from exc
    return dest


def stage_draft(
    workspace: Path,
    intended_path: str,
    content: str | bytes,
    *,
    agent_role: str | None = None,
    phase: str | None = None,
) -> DraftRecord:
    """Write *content* into the draft area. Does not touch the live path."""
    import hashlib

    _safe_intended_path(workspace, intended_path)
    root = _drafts_root(workspace)
    root.mkdir(parents=True, exist_ok=True)
    draft_id = uuid.uuid4().hex
    data = content.encode("utf-8") if isinstance(content, str) else content
    blob = root / draft_id
    blob.write_bytes(data)
    record = DraftRecord(
        draft_id=draft_id,
        intended_path=intended_path,
        sha256=hashlib.sha256(data).hexdigest(),
        created_at=datetime.now(UTC),
        agent_role=agent_role,
        phase=phase,
    )
    manifest = root / f"{draft_id}.{MANIFEST_NAME}"
    manifest.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    logger.info(
        "draft_staged",
        draft_id=draft_id,
        intended_path=intended_path,
        bytes=len(data),
    )
    return record


def load_draft(workspace: Path, draft_id: str) -> tuple[DraftRecord, bytes]:
    """Load a draft record and its bytes."""
    root = _drafts_root(workspace)
    manifest = root / f"{draft_id}.{MANIFEST_NAME}"
    blob = root / draft_id
    if not manifest.is_file() or not blob.is_file():
        raise FileNotFoundError(f"Draft not found: {draft_id}")
    record = DraftRecord.model_validate_json(manifest.read_text(encoding="utf-8"))
    return record, blob.read_bytes()


def commit_draft(workspace: Path, draft_id: str) -> str:
    """Promote a draft into the live workspace via ``os.replace``.

    Returns:
        The relative intended path that was committed.

    Raises:
        ValueError: Path validation failed.
        FileNotFoundError: Unknown draft id.
    """
    record, data = load_draft(workspace, draft_id)
    dest = _safe_intended_path(workspace, record.intended_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + f".{draft_id}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, dest)
    root = _drafts_root(workspace)
    (root / draft_id).unlink(missing_ok=True)
    (root / f"{draft_id}.{MANIFEST_NAME}").unlink(missing_ok=True)
    logger.info("draft_committed", draft_id=draft_id, path=record.intended_path)
    return record.intended_path


def discard_draft(workspace: Path, draft_id: str) -> None:
    """Remove a staged draft without committing it."""
    root = _drafts_root(workspace)
    (root / draft_id).unlink(missing_ok=True)
    (root / f"{draft_id}.{MANIFEST_NAME}").unlink(missing_ok=True)


def commit_pending_drafts(*, phase: str | None = None) -> CommitResult:
    """Promote every staged draft in the active run workspace (harness-owned commit).

    Draft-then-commit (seven-layer-harness R5.3) says drafts are promoted *after policy
    checks*. No backend gave agents ``commit_write``, and nothing else called it, so from
    2026-08-28 every agent write stayed a draft: tests were never collected and LangGraph /
    CrewAI runs looped (found by the 2026-09-16 course test). Callers invoke this once a
    phase's checks have passed. Each promotion goes through the bus as ``commit_write`` with
    ``agent_role="_harness"``, so it is audited like any other write.

    When one path was drafted several times, the newest draft wins and older ones are
    discarded.
    """
    from ai_team.config.settings import get_workspace_dir
    from ai_team.tools.bus import get_bus
    from ai_team.tools.kinds import ToolObservation, ToolRequest

    workspace = Path(get_workspace_dir())
    latest: dict[str, DraftRecord] = {}
    stale: list[DraftRecord] = []
    for record in sorted(list_drafts(workspace), key=lambda r: r.created_at):
        prev = latest.get(record.intended_path)
        if prev is not None:
            stale.append(prev)
        latest[record.intended_path] = record

    result = CommitResult(ok=True)
    for record in stale:
        discard_draft(workspace, record.draft_id)
    for record in latest.values():
        obs = get_bus().invoke(
            ToolRequest(
                tool="commit_write",
                args={"draft_id": record.draft_id},
                agent_role="_harness",
                phase=phase,
            )
        )
        assert isinstance(obs, ToolObservation)
        if obs.ok:
            result.committed.append(record.intended_path)
        else:
            result.ok = False
            result.rejected.append(record.intended_path)
            result.errors.append(obs.summary)
    if result.committed or result.rejected:
        logger.info(
            "drafts_committed",
            phase=phase,
            committed=len(result.committed),
            rejected=len(result.rejected),
            superseded=len(stale),
        )
    return result


def list_drafts(workspace: Path) -> list[DraftRecord]:
    """Return all staged drafts under *workspace*."""
    root = _drafts_root(workspace)
    if not root.is_dir():
        return []
    out: list[DraftRecord] = []
    for path in sorted(root.glob(f"*.{MANIFEST_NAME}")):
        try:
            out.append(DraftRecord.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, json.JSONDecodeError):
            logger.warning("draft_manifest_unreadable", path=str(path))
    return out


def draft_writes_enabled() -> bool:
    """Return whether draft-then-commit is on (default **on**)."""
    raw = os.environ.get("AI_TEAM_DRAFT_WRITES", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def irreversible_allowed_from_env() -> bool:
    """Test/ops escape hatch for irreversible tools. Default off."""
    raw = os.environ.get("AI_TEAM_ALLOW_IRREVERSIBLE", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def dump_manifests(workspace: Path) -> list[dict[str, Any]]:
    """Serialize current drafts for tests and receipts."""
    return [r.model_dump(mode="json") for r in list_drafts(workspace)]
