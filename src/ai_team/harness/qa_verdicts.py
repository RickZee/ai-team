"""Structured QA verdicts (R16) — one JSONL record per item per QA pass."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import structlog
from ai_team.harness.acceptance import VerifierIdentity
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

QA_VERDICTS_REL = Path("docs") / "qa_verdicts.jsonl"
IssueSeverity = Literal["blocker", "major", "minor", "info"]
Verdict = Literal["accept", "reject"]


class QaIssue(BaseModel):
    """One finding recorded by the in-run QA agent."""

    description: str
    severity: IssueSeverity
    evidence: list[str] = Field(default_factory=list)


class QaVerdict(BaseModel):
    """Structured verdict for one acceptance item."""

    item_id: str
    verdict: Verdict
    issues: list[QaIssue] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    qa_prompt_hash: str
    identity: VerifierIdentity
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def prompt_hash(prompt: str) -> str:
    """Stable sha256 of the QA prompt text (R16.6)."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def verdicts_path(workspace: Path) -> Path:
    """Return ``docs/qa_verdicts.jsonl`` under *workspace*."""
    return workspace / QA_VERDICTS_REL


def append_verdict(workspace: Path, verdict: QaVerdict) -> Path:
    """Append one structured verdict. Creates the file if needed."""
    path = verdicts_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(verdict.model_dump(mode="json"), default=str) + "\n")
    logger.info("qa_verdict_written", item_id=verdict.item_id, verdict=verdict.verdict)
    return path


def load_verdicts(workspace: Path) -> list[QaVerdict]:
    """Load verdicts; missing file is an empty list (Trace assembly tolerates absence)."""
    path = verdicts_path(workspace)
    if not path.is_file():
        return []
    out: list[QaVerdict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(QaVerdict.model_validate_json(line))
        except (ValueError, TypeError):
            continue
    return out


def emit_verdicts_from_acceptance(workspace: Path, *, session_id: str = "finalize") -> Path:
    """Write ``docs/qa_verdicts.jsonl`` from ``ACCEPTANCE.json`` (default-path producer).

    Missing acceptance is an empty file so the parser has a producer rather than
    absence. Never raises.
    """
    from ai_team.harness.acceptance import load

    identity = VerifierIdentity(agent_role="qa_engineer", session_id=session_id)
    hashed = prompt_hash("harness-finalize")
    path = verdicts_path(workspace)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return path
        items = []
        try:
            items = load(workspace).items
        except Exception:  # noqa: BLE001 — absence is empty, not an error
            items = []
        lines: list[str] = []
        for item in items:
            verdict = QaVerdict(
                item_id=item.id,
                verdict="accept" if item.passes else "reject",
                issues=(
                    []
                    if item.passes
                    else [
                        QaIssue(
                            description="not verified at finalize",
                            severity="major",
                            evidence=list(item.steps),
                        )
                    ]
                ),
                evidence=list(item.steps),
                qa_prompt_hash=hashed,
                identity=identity,
            )
            lines.append(json.dumps(verdict.model_dump(mode="json"), default=str))
        path.write_text(("\n".join(lines) + ("\n" if lines else "")), encoding="utf-8")
        logger.info("qa_verdicts_emitted", count=len(lines))
    except Exception as exc:  # noqa: BLE001 — producer must never abort a run
        logger.warning("qa_verdicts_emit_failed", error=str(exc))
    return path
