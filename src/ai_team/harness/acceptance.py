"""Durable, harness-owned acceptance list (ACCEPTANCE.json).

The harness is the only writer. Agents mutate ``passes`` solely through
``mark_passing`` (false → true with evidence). Demotion (true → false) is
harness-issued from the session regression check.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import structlog
from ai_team.models.requirements import MoSCoW, RequirementsDocument
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

ACCEPTANCE_FILENAME = "ACCEPTANCE.json"
ACCEPTANCE_LOG = Path("logs") / "acceptance.jsonl"
ACCEPTANCE_LOCK = Path("logs") / ".acceptance.lock"
SCHEMA_VERSION = 1

Category = Literal["functional", "style", "security", "performance"]
VerifiedBy = Literal["smoke", "ui_smoke", "test", "qa_agent"]

_MOSCOW_PRIORITY: dict[MoSCoW, int] = {
    MoSCoW.MUST: 0,
    MoSCoW.SHOULD: 1,
    MoSCoW.COULD: 2,
    MoSCoW.WONT: 3,
}
_NFR_CATEGORY: dict[str, Category] = {
    "security": "security",
    "performance": "performance",
    "style": "style",
    "usability": "style",
    "functional": "functional",
}
_PUNCT_SPACE_RE = re.compile(r"\s*([,.;:!?])\s*")


class AcceptanceError(ValueError):
    """Raised when an acceptance mutation is rejected."""


class VerifierIdentity(BaseModel):
    """Who produced the verifying evidence for a ``passes`` transition (R12.2)."""

    agent_role: str = Field(description="Role that recorded the evidence")
    session_id: str = Field(description="Session that recorded the evidence")
    subagent_id: str | None = Field(default=None, description="Subagent id if any")


class Demotion(BaseModel):
    """Harness-issued true → false record (R6.5 / R9)."""

    session_id: str = Field(description="Session that detected the regression")
    reason: str = Field(description="Why the item was demoted")
    detected_at: datetime = Field(description="UTC timestamp of the demotion")


class AcceptanceItem(BaseModel):
    """One monotonic acceptance criterion."""

    id: str = Field(description="Stable content hash of description + steps")
    category: Category = Field(description="functional | style | security | performance")
    description: str = Field(description="Human-readable criterion")
    steps: list[str] = Field(default_factory=list, description="Verification steps")
    priority: int = Field(default=0, description="Lower is higher priority")
    passes: bool = False
    verified_by: VerifiedBy | None = None
    verified_at: datetime | None = None
    verifier_identity: VerifierIdentity | None = None
    evidence: list[str] = Field(default_factory=list)
    demotions: list[Demotion] = Field(default_factory=list)


class AcceptanceList(BaseModel):
    """Workspace-root ACCEPTANCE.json document."""

    schema_version: int = SCHEMA_VERSION
    run_id: str
    created_at: datetime
    source: Literal["planning"] = "planning"
    items: list[AcceptanceItem] = Field(default_factory=list)


class AcceptanceStatus(BaseModel):
    """Read-only orientation for agents (R6.6)."""

    total: int
    passing: int
    unsatisfied: int
    next_item: AcceptanceItem | None = None


def normalize_for_id(text: str) -> str:
    """Collapse whitespace and punctuation spacing so cosmetic edits keep identity."""
    collapsed = " ".join((text or "").split())
    collapsed = _PUNCT_SPACE_RE.sub(r"\1 ", collapsed)
    return collapsed.strip()


def item_id(description: str, steps: list[str] | None = None) -> str:
    """Return ``sha256(normalized_description + NUL-joined steps)[:12]``."""
    parts = [normalize_for_id(description)]
    parts.extend(normalize_for_id(s) for s in (steps or []))
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()
    return digest[:12]


def acceptance_path(workspace: Path) -> Path:
    """Return the harness-owned ACCEPTANCE.json path."""
    return workspace / ACCEPTANCE_FILENAME


def _lock_path(workspace: Path) -> Path:
    path = workspace / ACCEPTANCE_LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _acquire_lock(workspace: Path) -> Any:
    """Return an open lock file with an exclusive flock held."""
    lock = _lock_path(workspace).open("a+b")
    try:
        import fcntl

        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    except OSError:
        # Windows / no flock: still serialize via exclusive create best-effort.
        pass
    return lock


def _release_lock(lock: Any) -> None:
    try:
        import fcntl

        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    except (OSError, ValueError):
        pass
    lock.close()


def _atomic_write(path: Path, payload: str) -> str:
    """Write *payload* via temp + ``os.replace``. Returns sha256 of the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = payload.encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(prefix=".acceptance-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return hashlib.sha256(data).hexdigest()


def _append_log(
    workspace: Path,
    op: str,
    item_id_value: str | None,
    file_sha: str,
    doc: AcceptanceList | None = None,
) -> None:
    log_path = workspace / ACCEPTANCE_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = None
    if doc is not None:
        snapshot = [
            {
                "id": i.id,
                "description": i.description,
                "steps": list(i.steps),
                "passes": i.passes,
                "evidence": list(i.evidence),
                "demotions": [d.model_dump(mode="json") for d in i.demotions],
            }
            for i in doc.items
        ]
    row = {
        "ts": datetime.now(UTC).isoformat(),
        "op": op,
        "item_id": item_id_value,
        "sha256_of_file": file_sha,
        "snapshot": snapshot,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def _dump(doc: AcceptanceList) -> str:
    return json.dumps(doc.model_dump(mode="json"), indent=2, default=str) + "\n"


def _write_locked(workspace: Path, doc: AcceptanceList, op: str, item_id_value: str | None) -> str:
    sha = _atomic_write(acceptance_path(workspace), _dump(doc))
    _append_log(workspace, op, item_id_value, sha, doc)
    return sha


def items_from_requirements(requirements: RequirementsDocument) -> list[AcceptanceItem]:
    """Derive acceptance items from a planning ``RequirementsDocument``.

    Priority follows MoSCoW (Must=0 … Won't=3); stories without criteria still
    contribute a single item from the story text. NFRs become items with a
    category inferred from their ``category`` field.
    """
    items: list[AcceptanceItem] = []
    seen: set[str] = set()

    def _add(description: str, *, category: Category, priority: int, steps: list[str]) -> None:
        iid = item_id(description, steps)
        if iid in seen:
            return
        seen.add(iid)
        items.append(
            AcceptanceItem(
                id=iid,
                category=category,
                description=description.strip(),
                steps=steps,
                priority=priority,
            )
        )

    for story in requirements.user_stories:
        priority = _MOSCOW_PRIORITY.get(story.priority, len(items))
        if story.acceptance_criteria:
            for criterion in story.acceptance_criteria:
                _add(criterion.description, category="functional", priority=priority, steps=[])
        else:
            desc = f"As a {story.as_a}, I want {story.i_want} so that {story.so_that}"
            _add(desc, category="functional", priority=priority, steps=[])

    for nfr in requirements.non_functional_requirements:
        cat = _NFR_CATEGORY.get(nfr.category.strip().lower(), "functional")
        _add(nfr.description, category=cat, priority=len(items), steps=[])

    return items


def items_from_mapping(raw: dict[str, Any]) -> list[AcceptanceItem]:
    """Best-effort extraction from a loosely-shaped planning dict (LangGraph)."""
    items: list[AcceptanceItem] = []
    seen: set[str] = set()

    def _push(description: str, priority: int, category: Category = "functional") -> None:
        desc = str(description).strip()
        if not desc:
            return
        iid = item_id(desc, [])
        if iid in seen:
            return
        seen.add(iid)
        items.append(AcceptanceItem(id=iid, category=category, description=desc, priority=priority))

    criteria = raw.get("acceptance_criteria") or []
    if isinstance(criteria, list):
        for i, c in enumerate(criteria):
            if isinstance(c, str):
                _push(c, i)
            elif isinstance(c, dict):
                _push(str(c.get("description") or c.get("criterion") or ""), i)

    functional = raw.get("functional") or []
    if isinstance(functional, list):
        for i, c in enumerate(functional):
            _push(str(c) if not isinstance(c, dict) else str(c.get("description") or ""), i)

    stories = raw.get("user_stories") or []
    if isinstance(stories, list):
        for i, story in enumerate(stories):
            if not isinstance(story, dict):
                continue
            acs = story.get("acceptance_criteria") or []
            if isinstance(acs, list) and acs:
                for c in acs:
                    text = c if isinstance(c, str) else str((c or {}).get("description") or "")
                    _push(text, i)
            else:
                _push(str(story.get("i_want") or story.get("description") or ""), i)

    if not items and raw.get("description"):
        _push(str(raw["description"]), 0)
    return items


def write_initial(
    workspace: Path,
    requirements: RequirementsDocument,
    run_id: str,
) -> AcceptanceList:
    """Write ACCEPTANCE.json at the end of planning. Refuses to overwrite."""
    existing = acceptance_path(workspace)
    if existing.is_file():
        raise AcceptanceError("ACCEPTANCE.json already exists; refusing to regenerate")
    items = items_from_requirements(requirements)
    if not items:
        items = [
            AcceptanceItem(
                id=item_id(requirements.project_name or "planned work", []),
                category="functional",
                description=requirements.project_name or requirements.description or "planned work",
                priority=0,
            )
        ]
    doc = AcceptanceList(
        run_id=run_id,
        created_at=datetime.now(UTC),
        items=items,
    )
    lock = _acquire_lock(workspace)
    try:
        _write_locked(workspace, doc, "write_initial", None)
    finally:
        _release_lock(lock)
    logger.info(
        "acceptance_written",
        run_id=run_id,
        items=len(doc.items),
        path=str(acceptance_path(workspace)),
    )
    return doc


def write_initial_from_any(
    workspace: Path,
    requirements: RequirementsDocument | dict[str, Any] | None,
    run_id: str,
) -> AcceptanceList | None:
    """Write ACCEPTANCE.json from a typed doc or a planning dict. No-op if present."""
    if acceptance_path(workspace).is_file():
        return load(workspace)
    if isinstance(requirements, RequirementsDocument):
        return write_initial(workspace, requirements, run_id)
    if isinstance(requirements, dict) and requirements:
        items = items_from_mapping(requirements)
        if not items:
            return None
        doc = AcceptanceList(run_id=run_id, created_at=datetime.now(UTC), items=items)
        lock = _acquire_lock(workspace)
        try:
            _write_locked(workspace, doc, "write_initial", None)
        finally:
            _release_lock(lock)
        logger.info("acceptance_written", run_id=run_id, items=len(doc.items))
        return doc
    return None


def load(workspace: Path) -> AcceptanceList:
    """Load ACCEPTANCE.json. Raises if missing or corrupt."""
    path = acceptance_path(workspace)
    if not path.is_file():
        raise AcceptanceError(f"ACCEPTANCE.json missing under {workspace}")
    try:
        return AcceptanceList.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AcceptanceError(f"ACCEPTANCE.json corrupt: {exc}") from exc


def mark_passing(
    workspace: Path,
    item_id_value: str,
    *,
    evidence: list[str],
    verified_by: VerifiedBy,
    identity: VerifierIdentity,
) -> AcceptanceList:
    """Permit the single agent-driven mutation: ``passes: false → true`` with evidence."""
    if not evidence:
        raise AcceptanceError("mark_passing requires at least one evidence path")
    # Evidence must resolve inside the workspace (relative or absolute-under-root).
    resolved_missing: list[str] = []
    for rel in evidence:
        candidate = Path(rel)
        if candidate.is_absolute():
            try:
                candidate.relative_to(workspace.resolve())
            except ValueError:
                resolved_missing.append(rel)
                continue
            if not candidate.is_file():
                resolved_missing.append(rel)
        elif not (workspace / rel).is_file():
            resolved_missing.append(rel)
    if resolved_missing:
        raise AcceptanceError(f"evidence paths missing from workspace: {resolved_missing}")

    lock = _acquire_lock(workspace)
    try:
        doc = load(workspace)
        found = next((i for i in doc.items if i.id == item_id_value), None)
        if found is None:
            raise AcceptanceError(f"unknown acceptance item: {item_id_value}")
        if found.passes:
            raise AcceptanceError(f"item {item_id_value} already passes")
        found.passes = True
        found.verified_by = verified_by
        found.verified_at = datetime.now(UTC)
        found.verifier_identity = identity
        found.evidence = list(evidence)
        _write_locked(workspace, doc, "mark_passing", item_id_value)
        return doc
    finally:
        _release_lock(lock)


def demote(
    workspace: Path,
    item_id_value: str,
    *,
    session_id: str,
    reason: str,
) -> AcceptanceList:
    """Harness-issued demotion. Refuses without a reason."""
    if not (reason or "").strip():
        raise AcceptanceError("demote requires a non-empty reason")
    lock = _acquire_lock(workspace)
    try:
        doc = load(workspace)
        found = next((i for i in doc.items if i.id == item_id_value), None)
        if found is None:
            raise AcceptanceError(f"unknown acceptance item: {item_id_value}")
        if not found.passes:
            raise AcceptanceError(f"item {item_id_value} is not passing; cannot demote")
        found.passes = False
        found.demotions.append(
            Demotion(
                session_id=session_id,
                reason=reason.strip(),
                detected_at=datetime.now(UTC),
            )
        )
        _write_locked(workspace, doc, "demote", item_id_value)
        return doc
    finally:
        _release_lock(lock)


def status(workspace: Path) -> AcceptanceStatus:
    """Return counts and the highest-priority unsatisfied item."""
    doc = load(workspace)
    unsatisfied = [i for i in doc.items if not i.passes]
    unsatisfied.sort(key=lambda i: (i.priority, i.id))
    passing = sum(1 for i in doc.items if i.passes)
    return AcceptanceStatus(
        total=len(doc.items),
        passing=passing,
        unsatisfied=len(unsatisfied),
        next_item=unsatisfied[0] if unsatisfied else None,
    )


def is_acceptance_target(workspace: Path, file_path: str) -> bool:
    """True when *file_path* resolves to the harness-owned ACCEPTANCE.json."""
    raw = (file_path or "").strip()
    if not raw:
        return False
    target = acceptance_path(workspace).resolve()
    candidates = [Path(raw)]
    if not Path(raw).is_absolute():
        candidates.append(workspace / raw)
        candidates.append(Path(raw.replace("./", "", 1)))
        candidates.append(workspace / raw.replace("./", "", 1))
    for cand in candidates:
        try:
            resolved = cand.resolve()
        except OSError:
            continue
        if resolved == target:
            return True
        # Compare after resolving a symlink that may not yet exist as target.
        try:
            if cand.is_symlink() and cand.resolve() == target:
                return True
        except OSError:
            continue
    # Name-only match when the file lives at the workspace root.
    name = Path(raw).name
    if name == ACCEPTANCE_FILENAME and ".." not in Path(raw).parts:
        parent = Path(raw).parent
        if str(parent) in {".", "", str(workspace), str(workspace.resolve())}:
            return True
    return False
