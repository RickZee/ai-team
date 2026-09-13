"""Build-contract store: file-based developer/QA handoff (R11).

Round ceiling is enforced here. The PreToolUse hook calls
``require_accepted``; when the component is ablated the hook is a no-op.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

MAX_ROUNDS = 2
CONTRACTS_DIR = Path("docs") / "contracts"
CONTRACT_GATE_ENV = "AI_TEAM_CONTRACT_GATE"


class ContractReview(BaseModel):
    """QA verdict on one contract draft."""

    verdict: Literal["accepted", "rejected"]
    reasons: list[str] = Field(default_factory=list)
    reviewed_at: datetime
    reviewer: str = "qa_engineer"


class BuildContract(BaseModel):
    """One item's negotiated build contract."""

    item_id: str
    round: int
    approach: str
    testable_behaviors: list[str] = Field(default_factory=list)
    files_to_touch: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    review: ContractReview | None = None


class ContractRoundCeilingError(ValueError):
    """Raised when a third negotiation round is attempted."""


class ContractError(ValueError):
    """Invalid contract store operation."""


def contract_gate_enabled() -> bool:
    """True when the contract gate is explicitly on (off by default)."""
    return os.environ.get(CONTRACT_GATE_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def contracts_dir(workspace: Path) -> Path:
    """Return ``docs/contracts`` under *workspace*."""
    return workspace / CONTRACTS_DIR


def contract_path(workspace: Path, item_id: str) -> Path:
    """Return ``docs/contracts/<item_id>.json``."""
    safe = item_id.replace("/", "_")
    return contracts_dir(workspace) / f"{safe}.json"


def load_contract(workspace: Path, item_id: str) -> BuildContract | None:
    """Load one contract, or None if absent."""
    path = contract_path(workspace, item_id)
    if not path.is_file():
        return None
    try:
        return BuildContract.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("contract_load_failed", path=str(path), error=str(exc))
        return None


def write_contract(workspace: Path, contract: BuildContract) -> Path:
    """Persist a contract. Raises if the round ceiling would be exceeded."""
    if contract.round > MAX_ROUNDS:
        raise ContractRoundCeilingError(
            f"contract round {contract.round} exceeds ceiling {MAX_ROUNDS}"
        )
    existing = load_contract(workspace, contract.item_id)
    if existing is not None and existing.round >= MAX_ROUNDS:
        accepted = existing.review is not None and existing.review.verdict == "accepted"
        if not accepted and contract.round > existing.round:
            raise ContractRoundCeilingError(
                f"item {contract.item_id} already used {MAX_ROUNDS} rounds"
            )
    dest = contract_path(workspace, contract.item_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(contract.model_dump_json(indent=2), encoding="utf-8")
    logger.info("contract_written", item_id=contract.item_id, round=contract.round)
    return dest


def review_contract(
    workspace: Path,
    item_id: str,
    *,
    verdict: Literal["accepted", "rejected"],
    reasons: list[str],
    reviewer: str = "qa_engineer",
) -> BuildContract:
    """Attach a QA review to the current contract."""
    current = load_contract(workspace, item_id)
    if current is None:
        raise ContractError(f"no contract for {item_id}")
    current.review = ContractReview(
        verdict=verdict,
        reasons=reasons,
        reviewed_at=datetime.now(UTC),
        reviewer=reviewer,
    )
    write_contract(workspace, current)
    return current


def require_accepted(workspace: Path, item_id: str) -> bool:
    """True when *item_id* has an accepted contract."""
    current = load_contract(workspace, item_id)
    return bool(current and current.review and current.review.verdict == "accepted")


def accepted_covers_path(workspace: Path, file_path: str) -> bool:
    """True when some accepted contract lists *file_path* in ``files_to_touch``."""
    root = contracts_dir(workspace)
    if not root.is_dir():
        return False
    rel = file_path.lstrip("./")
    for path in root.glob("*.json"):
        try:
            doc = BuildContract.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if doc.review is None or doc.review.verdict != "accepted":
            continue
        for listed in doc.files_to_touch:
            if rel == listed.lstrip("./") or rel.endswith(listed.lstrip("./")):
                return True
        if not doc.files_to_touch:
            return True
    return False


def negotiate(
    workspace: Path,
    item_id: str,
    *,
    propose: Any,
    review: Any,
    escalate: Any,
) -> BuildContract | None:
    """Run at most ``MAX_ROUNDS`` propose/review cycles, then escalate.

    ``propose(round) -> BuildContract``, ``review(contract) -> ContractReview``,
    ``escalate(item_id, reasons)`` is called instead of a third round.
    """
    last_reasons: list[str] = []
    for rnd in range(1, MAX_ROUNDS + 1):
        contract = propose(rnd)
        if not isinstance(contract, BuildContract):
            contract = BuildContract.model_validate(contract)
        contract.round = rnd
        contract.item_id = item_id
        write_contract(workspace, contract)
        verdict = review(contract)
        if not isinstance(verdict, ContractReview):
            verdict = ContractReview.model_validate(verdict)
        contract.review = verdict
        write_contract(workspace, contract)
        if verdict.verdict == "accepted":
            return contract
        last_reasons = list(verdict.reasons)
    escalate(item_id, last_reasons)
    return None
