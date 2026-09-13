"""Multi-session continuation: reset, don't compact (R8 / R9).

Off by default. Requires an explicit ``max_sessions`` and a total budget.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import structlog
from ai_team.harness.acceptance import AcceptanceItem, demote, load, status
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

SESSIONS_LOG = Path("logs") / "sessions.jsonl"
SESSION_LOOP_ENV = "AI_TEAM_SESSION_LOOP"
SessionStatus = Literal["ok", "dirty_exit", "error", "budget_exhausted"]


class SessionRecord(BaseModel):
    """One session's durable record (design §3.2)."""

    session_id: str
    index: int
    started_at: datetime
    ended_at: datetime
    status: SessionStatus
    items_attempted: list[str] = Field(default_factory=list)
    items_passed: list[str] = Field(default_factory=list)
    items_demoted: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    context_pressure_at_end: float | None = None
    termination_reason: str = ""


class SessionBackend(Protocol):
    """Minimal backend used by the session loop (stubbed in tests)."""

    def run_session(
        self,
        workspace: Path,
        *,
        context: str,
        item_id: str | None,
        session_index: int,
    ) -> dict[str, Any]:
        """Execute one fresh-context session and return a result dict."""
        ...


def session_loop_flag_enabled() -> bool:
    """True when ``AI_TEAM_SESSION_LOOP`` is set to a truthy value."""
    return os.environ.get(SESSION_LOOP_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def sessions_enabled(max_sessions: int | None) -> bool:
    """The loop stays off unless the env flag is on *and* ``max_sessions`` is > 1."""
    return session_loop_flag_enabled() and bool(max_sessions and max_sessions > 1)


def append_session_record(workspace: Path, record: SessionRecord) -> None:
    """Append one JSON line to ``logs/sessions.jsonl``."""
    path = workspace / SESSIONS_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(record.model_dump_json() + "\n")


def load_session_records(workspace: Path) -> list[SessionRecord]:
    """Load session records; missing file is empty, not an error."""
    path = workspace / SESSIONS_LOG
    if not path.is_file():
        return []
    out: list[SessionRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(SessionRecord.model_validate_json(line))
        except ValueError:
            continue
    return out


def build_fresh_context(workspace: Path) -> str:
    """Re-derive context from the four files plus git log. No summarizer."""
    parts: list[str] = []
    for rel in ("docs/CONSTRAINTS.md", "docs/STATE.md", "docs/LESSONS.md", "ACCEPTANCE.json"):
        path = workspace / rel
        if path.is_file():
            parts.append(f"# {rel}\n{path.read_text(encoding='utf-8', errors='replace')}")
    try:
        git_log = subprocess.run(  # noqa: S603
            ["git", "log", "--oneline", "-n", "20"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        if git_log.returncode == 0 and git_log.stdout.strip():
            parts.append(f"# git log\n{git_log.stdout}")
    except OSError:
        pass
    return "\n\n".join(parts)


def workspace_is_dirty(workspace: Path) -> bool:
    """True when git reports uncommitted changes (or git is absent)."""
    try:
        proc = subprocess.run(  # noqa: S603
            ["git", "status", "--porcelain"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return True
    if proc.returncode != 0:
        return True
    return bool(proc.stdout.strip())


def commit_session(workspace: Path, message: str) -> bool:
    """Create a session-end commit. Returns False if nothing to commit or git fails."""
    try:
        subprocess.run(["git", "add", "-A"], cwd=workspace, check=False, capture_output=True)
        proc = subprocess.run(  # noqa: S603
            ["git", "commit", "-m", message],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode == 0
    except OSError:
        return False


def select_regression_targets(
    workspace: Path,
    *,
    rng: random.Random,
    lookback: int = 2,
) -> list[str]:
    """Highest-priority passing item plus one seeded-random item not recently verified."""
    try:
        doc = load(workspace)
    except Exception:  # noqa: BLE001 — no list yet
        return []
    passing = [i for i in doc.items if i.passes]
    passing.sort(key=lambda i: i.priority)
    chosen: list[str] = []
    if passing:
        chosen.append(passing[0].id)
    recent = _recently_verified(workspace, lookback)
    pool = [i.id for i in passing if i.id not in chosen and i.id not in recent]
    if pool:
        chosen.append(rng.choice(pool))
    elif passing and passing[0].id not in chosen:
        chosen.append(passing[0].id)
    return chosen


def _recently_verified(workspace: Path, lookback: int) -> set[str]:
    records = load_session_records(workspace)[-lookback:]
    seen: set[str] = set()
    for rec in records:
        seen.update(rec.items_passed)
        seen.update(rec.items_attempted)
    return seen


def prioritize_demoted(workspace: Path) -> AcceptanceItem | None:
    """Next work item: demoted first, then the next unsatisfied item."""
    try:
        doc = load(workspace)
    except Exception:  # noqa: BLE001
        return None
    demoted = [i for i in doc.items if i.demotions and not i.passes]
    demoted.sort(key=lambda i: i.priority)
    if demoted:
        return demoted[0]
    return status(workspace).next_item


def run_sessions(
    workspace: Path,
    *,
    backend: SessionBackend,
    max_sessions: int,
    total_budget_usd: float,
    no_progress_sessions: int = 2,
    regression_k: int = 2,
    rng: random.Random | None = None,
    verify: Any | None = None,
    wall_clock_s: float | None = None,
) -> list[SessionRecord]:
    """Run fresh-context sessions until a termination condition fires.

    Termination (checked *before* the next session): all-pass, ``max_sessions``,
    spend, wall-clock, or ``no_progress_sessions``.
    """
    if not sessions_enabled(max_sessions):
        raise ValueError("run_sessions requires explicit --max-sessions > 1")
    if total_budget_usd <= 0:
        raise ValueError("run_sessions requires a total budget")

    rng = rng or random.Random(0)
    records: list[SessionRecord] = []
    spent = 0.0
    no_progress = 0
    started_all = datetime.now(UTC)

    for index in range(max_sessions):
        if spent >= total_budget_usd:
            break
        if wall_clock_s is not None:
            elapsed = (datetime.now(UTC) - started_all).total_seconds()
            if elapsed >= wall_clock_s:
                break
        try:
            st = status(workspace)
            if st.unsatisfied == 0 and st.total > 0:
                break
        except Exception:  # noqa: BLE001
            st = None
        if no_progress >= no_progress_sessions:
            break

        context = build_fresh_context(workspace)
        targets = select_regression_targets(workspace, rng=rng, lookback=regression_k)
        item = prioritize_demoted(workspace)
        item_id = item.id if item else None
        started = datetime.now(UTC)
        result = backend.run_session(
            workspace,
            context=context,
            item_id=item_id,
            session_index=index,
        )
        cost = float(result.get("cost_usd") or 0.0)
        spent += cost
        passed_ids = list(result.get("items_passed") or [])
        demoted_ids: list[str] = []
        if verify is not None:
            for tid in targets:
                ok = bool(verify(workspace, tid))
                if not ok:
                    demote(
                        workspace,
                        tid,
                        session_id=f"session-{index}",
                        reason="regression_check failed",
                    )
                    demoted_ids.append(tid)
        dirty = workspace_is_dirty(workspace)
        if dirty and not result.get("skip_commit"):
            committed = commit_session(workspace, f"session {index}")
            dirty = not committed and workspace_is_dirty(workspace)

        if result.get("budget_exhausted"):
            sess_status: SessionStatus = "budget_exhausted"
            reason = "spend"
        elif result.get("error"):
            sess_status = "error"
            reason = str(result.get("error"))
        elif dirty:
            sess_status = "dirty_exit"
            reason = "uncommitted_changes"
            _emit_dirty_write_span(workspace)
        else:
            sess_status = "ok"
            reason = "session_complete"

        if not passed_ids and not demoted_ids:
            no_progress += 1
        else:
            no_progress = 0

        record = SessionRecord(
            session_id=str(result.get("session_id") or f"session-{index}"),
            index=index,
            started_at=started,
            ended_at=datetime.now(UTC),
            status=sess_status,
            items_attempted=[item_id] if item_id else [],
            items_passed=passed_ids,
            items_demoted=demoted_ids,
            cost_usd=cost,
            context_pressure_at_end=result.get("context_pressure"),
            termination_reason=reason,
        )
        append_session_record(workspace, record)
        records.append(record)
        if sess_status in {"budget_exhausted", "error"}:
            break
    return records


def _emit_dirty_write_span(workspace: Path) -> None:
    """Leave an audit row so ``CHK-draft-commit`` (FM-012) can fire."""
    audit = workspace / "logs" / "audit.jsonl"
    audit.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(UTC).isoformat(),
        "kind": "write",
        "code": "ok",
        "result": "ok",
        "tool": "write_file",
        "path": "src/uncommitted.py",
        "phase": "development",
    }
    with audit.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
