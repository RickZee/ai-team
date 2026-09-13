"""Change receipt: disk is the source of truth for a run (FM-008)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

RECEIPT_SCHEMA_VERSION = 1


class RouteRecord(BaseModel):
    """One model route used during the run."""

    phase: str | None = None
    task_type: str | None = None
    model_id: str
    same_model: bool = False


class GuardrailEvidence(BaseModel):
    """Auditor artifact: policy, checks fired, overrides, outcomes."""

    policy_version: str = "unspecified"
    checks: list[dict[str, Any]] = Field(default_factory=list)
    overrides: list[str] = Field(default_factory=list)
    outcomes: list[dict[str, Any]] = Field(default_factory=list)
    tool_permission_set: list[str] = Field(default_factory=list)


class ChangeReceipt(BaseModel):
    """Normalized per-run receipt written next to ``run.json``."""

    schema_version: int = RECEIPT_SCHEMA_VERSION
    run_id: str
    backend: str
    team_profile: str = "full"
    policy_version: str = "unspecified"
    context_sources: list[str] = Field(default_factory=list)
    tool_permission_set: list[str] = Field(default_factory=list)
    routes: list[RouteRecord] = Field(default_factory=list)
    tests: dict[str, Any] = Field(default_factory=dict)
    smoke: dict[str, Any] = Field(default_factory=dict)
    overrides: list[str] = Field(default_factory=list)
    cost_usd: float | None = None
    cost_per_accepted_change: float | None = None
    failure_ids: list[str] = Field(default_factory=list)
    accepted: bool = False
    output_hash: str | None = None
    rollback_ref: str | None = None
    guardrail_evidence: GuardrailEvidence = Field(default_factory=GuardrailEvidence)
    provenance: dict[str, Any] = Field(default_factory=dict)
    acceptance_path: str | None = None
    acceptance_item_count: int | None = None
    written_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def compute_cost_per_accepted_change(
    *,
    total_usd: float | None,
    accepted_changes: int,
) -> float | None:
    """``total_usd / max(accepted_changes, 1)``. None if cost unknown."""
    if total_usd is None:
        return None
    denom = max(int(accepted_changes), 1)
    return round(float(total_usd) / denom, 6)


def is_accepted_change(
    *,
    smoke: dict[str, Any] | None,
    required_ok: bool,
    failure_ids: list[str] | None = None,
) -> bool:
    """R10.2: artifacts present, smoke success or skip-with-reason, no FM-001/006/012."""
    blocking = {"FM-001", "FM-006", "FM-012"}
    if failure_ids and blocking.intersection(failure_ids):
        return False
    if not required_ok:
        return False
    if not smoke:
        return False
    if smoke.get("success") is True:
        return True
    if smoke.get("ran") is False and smoke.get("skip_reason"):
        return True
    return False


def workspace_tree_hash(workspace: Path) -> str:
    """Stable hash of relative paths + sha256 of file bytes (small files)."""
    h = hashlib.sha256()
    if not workspace.is_dir():
        return h.hexdigest()
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        if ".harness" in path.parts or path.suffix in {".pyc"}:
            continue
        rel = str(path.relative_to(workspace))
        h.update(rel.encode("utf-8"))
        try:
            h.update(path.read_bytes()[: 256 * 1024])
        except OSError:
            continue
    return h.hexdigest()


def receipt_to_markdown(receipt: ChangeReceipt) -> str:
    """Human-readable receipt.md."""
    smoke = receipt.smoke.get("success")
    lines = [
        f"# Change receipt `{receipt.run_id}`",
        "",
        f"- backend: `{receipt.backend}`",
        f"- profile: `{receipt.team_profile}`",
        f"- accepted: **{receipt.accepted}**",
        f"- cost_usd: {receipt.cost_usd}",
        f"- cost_per_accepted_change: {receipt.cost_per_accepted_change}",
        f"- smoke: {smoke}",
        f"- failures: {', '.join(receipt.failure_ids) or 'none'}",
        f"- output_hash: `{receipt.output_hash or '—'}`",
        f"- rollback: `{receipt.rollback_ref or '—'}`",
        f"- acceptance: `{receipt.acceptance_path or '—'}` "
        f"({receipt.acceptance_item_count if receipt.acceptance_item_count is not None else '—'} items)",
        "",
        "## Routes",
        "",
    ]
    for route in receipt.routes:
        lines.append(f"- {route.phase or '—'} / {route.task_type or '—'} → `{route.model_id}`")
    if not receipt.routes:
        lines.append("- (none recorded)")
    lines.extend(["", "## Overrides", ""])
    for item in receipt.overrides:
        lines.append(f"- {item}")
    if not receipt.overrides:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


class ReceiptWriter:
    """Write ``receipt.json`` and ``receipt.md`` under an output run dir."""

    def write(self, output_dir: Path, receipt: ChangeReceipt) -> tuple[Path, Path]:
        """Persist receipt files. Creates *output_dir* if needed."""
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "receipt.json"
        md_path = output_dir / "receipt.md"
        json_path.write_text(
            json.dumps(receipt.model_dump(mode="json"), indent=2, default=str),
            encoding="utf-8",
        )
        md_path.write_text(receipt_to_markdown(receipt), encoding="utf-8")
        logger.info("receipt_written", run_id=receipt.run_id, path=str(json_path))
        return json_path, md_path

    def write_from_run(
        self,
        *,
        output_dir: Path,
        workspace: Path | None,
        run_id: str,
        backend: str,
        team_profile: str = "full",
        cost_usd: float | None = None,
        smoke: dict[str, Any] | None = None,
        tests: dict[str, Any] | None = None,
        routes: list[RouteRecord] | None = None,
        failure_ids: list[str] | None = None,
        overrides: list[str] | None = None,
        context_sources: list[str] | None = None,
        tool_permission_set: list[str] | None = None,
        guardrail_evidence: GuardrailEvidence | None = None,
        rollback_ref: str | None = None,
        required_ok: bool = True,
        provenance: dict[str, Any] | None = None,
    ) -> ChangeReceipt:
        """Build and write a receipt from run fields."""
        smoke_d = smoke or {}
        fails = failure_ids or []
        accepted = is_accepted_change(smoke=smoke_d, required_ok=required_ok, failure_ids=fails)
        accepted_n = 1 if accepted else 0
        output_hash = workspace_tree_hash(workspace) if workspace else None
        acceptance_path = None
        acceptance_item_count = None
        if workspace is not None:
            acc = workspace / "ACCEPTANCE.json"
            if acc.is_file():
                acceptance_path = "ACCEPTANCE.json"
                try:
                    payload = json.loads(acc.read_text(encoding="utf-8"))
                    items = payload.get("items") if isinstance(payload, dict) else None
                    if isinstance(items, list):
                        acceptance_item_count = len(items)
                except (OSError, ValueError, json.JSONDecodeError):
                    acceptance_item_count = None
        receipt = ChangeReceipt(
            run_id=run_id,
            backend=backend,
            team_profile=team_profile,
            context_sources=context_sources or [],
            tool_permission_set=tool_permission_set or [],
            routes=routes or [],
            tests=tests or {},
            smoke=smoke_d,
            overrides=overrides or [],
            cost_usd=cost_usd,
            cost_per_accepted_change=compute_cost_per_accepted_change(
                total_usd=cost_usd, accepted_changes=accepted_n
            ),
            failure_ids=fails,
            accepted=accepted,
            output_hash=output_hash,
            rollback_ref=rollback_ref,
            guardrail_evidence=guardrail_evidence or GuardrailEvidence(),
            provenance=provenance or {},
            acceptance_path=acceptance_path,
            acceptance_item_count=acceptance_item_count,
        )
        self.write(output_dir, receipt)
        return receipt


def load_receipt(output_dir: Path) -> ChangeReceipt | None:
    """Load ``receipt.json`` if present."""
    path = output_dir / "receipt.json"
    if not path.is_file():
        return None
    try:
        return ChangeReceipt.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("receipt_load_failed", path=str(path), error=str(exc))
        return None
