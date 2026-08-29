"""Context-layer checks: FM-011 constraint survival."""

from __future__ import annotations

from evals.checks.base import CheckResult, failed, na, passed
from evals.checks.registry import check
from evals.trace.models import Trace

_LATER = frozenset({"testing", "deployment"})


def _ids_from_span(payload: dict[str, object]) -> list[str]:
    raw = payload.get("constraint_ids")
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return []


@check(id="CHK-constraint-survival", failure_mode_id="FM-011", tier="A")
def constraint_survival(trace: Trace) -> CheckResult:
    """Fail when an intake constraint id is missing at testing or deployment."""
    cid = "CHK-constraint-survival"
    fm = "FM-011"
    starts = list(trace.spans_of("phase_start"))
    if not starts:
        return na(cid, trace, "no phase_start spans", failure_mode_id=fm)

    intake_ids: list[str] = []
    later: dict[str, list[str]] = {}
    for span in starts:
        ids = _ids_from_span(span.payload)
        if span.phase == "intake":
            intake_ids = ids
        elif span.phase in _LATER:
            later[str(span.phase)] = ids

    if not intake_ids:
        return na(cid, trace, "no intake constraint_ids", failure_mode_id=fm)
    if not later:
        return na(cid, trace, "no testing/deployment phase_start", failure_mode_id=fm)

    missing: list[str] = []
    evidence: list[str] = []
    for phase, ids in later.items():
        dropped = [i for i in intake_ids if i not in ids]
        if dropped:
            missing.extend(f"{phase}:{x}" for x in dropped)
            evidence.extend(s.span_id for s in starts if s.phase == phase)

    if missing:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_span_ids=evidence,
            evidence_text=f"constraint dropped: {missing}",
            detail={"missing": missing, "intake_ids": intake_ids},
        )
    return passed(cid, trace, failure_mode_id=fm, evidence_text="constraints survived")
