"""Harness-owned acceptance. A run's accept does not depend on a QA tool.

Quality-gate evidence (tests, lint, smoke) marks each criterion ``passing``,
``failing``, or ``unverified``. A criterion with no evidence stays
``unverified``. QA verdicts are a second signal; disagreements are logged.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

AcceptanceStatus = Literal["passing", "failing", "unverified"]
_PASSING_QA = frozenset({"accept", "accepted", "pass", "passing", "true"})
_FAILING_QA = frozenset({"reject", "rejected", "fail", "failing", "false"})


class Criterion(BaseModel):
    """One acceptance criterion, keyed the way the product owner wrote it."""

    id: str = Field(description="Stable criterion id.")
    description: str = Field(default="", description="Human-readable criterion.")


class CriterionEvidence(BaseModel):
    """Harness evidence for one criterion. Absent signals are not a pass."""

    tests_passed: bool | None = None
    lint_ok: bool | None = None
    smoke_ok: bool | None = None

    def status(self) -> AcceptanceStatus:
        """passing only when every present signal is true."""
        present = [
            value for value in (self.tests_passed, self.lint_ok, self.smoke_ok) if value is not None
        ]
        if not present:
            return "unverified"
        if any(value is False for value in present):
            return "failing"
        return "passing"


class AcceptanceResult(BaseModel):
    """Harness mark for one criterion, plus the QA verdict when one exists."""

    criterion_id: str
    status: AcceptanceStatus
    qa_verdict: str | None = None


def evaluate(
    criteria: list[Criterion],
    evidence: dict[str, CriterionEvidence],
    qa_verdicts: dict[str, str] | None = None,
) -> list[AcceptanceResult]:
    """Mark each criterion from evidence. Missing evidence is never passing.

    Args:
        criteria: Criteria to mark, in order.
        evidence: Map of criterion id to harness evidence. Ids not in the map
            are unverified even when other criteria have evidence.
        qa_verdicts: Optional QA verdict per criterion id (second signal).
    """
    verdicts = qa_verdicts or {}
    results: list[AcceptanceResult] = []
    for criterion in criteria:
        ev = evidence.get(criterion.id)
        status: AcceptanceStatus = "unverified" if ev is None else ev.status()
        results.append(
            AcceptanceResult(
                criterion_id=criterion.id,
                status=status,
                qa_verdict=verdicts.get(criterion.id),
            )
        )
    return results


def disagreements(results: list[AcceptanceResult]) -> list[AcceptanceResult]:
    """Results where QA and the harness disagree."""
    out: list[AcceptanceResult] = []
    for result in results:
        verdict = (result.qa_verdict or "").strip().lower()
        if not verdict:
            continue
        qa_pass = verdict in _PASSING_QA
        qa_fail = verdict in _FAILING_QA
        if (result.status == "passing" and qa_fail) or (result.status == "failing" and qa_pass):
            out.append(result)
    return out


def _load_criteria(workspace: Path) -> list[Criterion]:
    path = workspace / "ACCEPTANCE.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    criteria: list[Criterion] = []
    for item in items:
        if isinstance(item, dict) and item.get("id"):
            criteria.append(
                Criterion(id=str(item["id"]), description=str(item.get("description") or ""))
            )
    return criteria


def _write_disagreement_spans(workspace: Path, rows: list[AcceptanceResult]) -> None:
    path = workspace / "logs" / "qa_disagreements.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            payload = {
                "type": "qa_disagreement",
                "timestamp": now,
                "criterion_id": row.criterion_id,
                "harness_status": row.status,
                "qa_verdict": row.qa_verdict,
            }
            handle.write(json.dumps(payload) + "\n")


def apply_quality_gate_acceptance(
    workspace: Path,
    *,
    tests_passed: bool | None = None,
    lint_ok: bool | None = None,
    smoke_ok: bool | None = None,
    qa_verdicts: dict[str, str] | None = None,
    evidence_by_id: dict[str, CriterionEvidence] | None = None,
) -> list[AcceptanceResult]:
    """Record harness acceptance after the testing phase. Never raises.

    When the workspace has no criteria yet and the gate produced a boolean
    test result, one ``harness-tests`` criterion is marked from that result.
    That is the accept LangGraph and CrewAI were missing when QA had no tool.
    """
    try:
        return _apply(
            workspace,
            tests_passed=tests_passed,
            lint_ok=lint_ok,
            smoke_ok=smoke_ok,
            qa_verdicts=qa_verdicts,
            evidence_by_id=evidence_by_id,
        )
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("harness_acceptance_skipped", error=str(exc))
        return []


def _apply(
    workspace: Path,
    *,
    tests_passed: bool | None,
    lint_ok: bool | None,
    smoke_ok: bool | None,
    qa_verdicts: dict[str, str] | None,
    evidence_by_id: dict[str, CriterionEvidence] | None,
) -> list[AcceptanceResult]:
    criteria = _load_criteria(workspace)
    evidence: dict[str, CriterionEvidence] = dict(evidence_by_id or {})
    if not criteria and tests_passed is not None:
        criteria = [Criterion(id="harness-tests", description="pytest passed")]
    if tests_passed is not None or lint_ok is not None or smoke_ok is not None:
        shared = CriterionEvidence(
            tests_passed=tests_passed,
            lint_ok=lint_ok,
            smoke_ok=smoke_ok,
        )
        for criterion in criteria:
            evidence.setdefault(criterion.id, shared)
    results = evaluate(criteria, evidence, qa_verdicts)
    logs = workspace / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "results": [row.model_dump() for row in results],
    }
    (logs / "harness_acceptance.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    bad = disagreements(results)
    if bad:
        _write_disagreement_spans(workspace, bad)
        logger.info("qa_disagreement", count=len(bad))
    return results


def _bool_at(mapping: Any, key: str) -> bool | None:
    value = mapping.get(key) if isinstance(mapping, dict) else None
    return value if isinstance(value, bool) else None


def record_acceptance_from_state(workspace: Path, state: dict[str, Any]) -> None:
    """Acceptance from a ``test_results`` mapping (LangGraph state, Claude SDK raw). Never raises."""
    tr = state.get("test_results")
    lint = tr.get("lint") if isinstance(tr, dict) else None
    apply_quality_gate_acceptance(
        workspace, tests_passed=_bool_at(tr, "passed"), lint_ok=_bool_at(lint, "ok")
    )


def record_acceptance_from_test_result(workspace: Path, test_results: Any) -> None:
    """Acceptance from a CrewAI testing result object. Never raises."""
    tests_passed: bool | None = None
    success = getattr(test_results, "success", None)
    failed = getattr(test_results, "failed", None)
    passed = getattr(test_results, "passed", None)
    if isinstance(success, bool):
        tests_passed = success
    elif isinstance(failed, int) and isinstance(passed, int):
        tests_passed = failed == 0 and passed > 0
    apply_quality_gate_acceptance(workspace, tests_passed=tests_passed)
