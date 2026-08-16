"""Guardrail false-positive budget check: FM-005."""

from __future__ import annotations

from evals.checks.base import CheckResult, failed, na, passed
from evals.checks.registry import check
from evals.trace.models import Trace


def _acceptance_met(trace: Trace) -> bool:
    """Heuristic: complete status and at least one source/test artifact."""
    if trace.status != "complete":
        return False
    produced = [a for a in trace.files() if a.kind in {"source", "test"}]
    return bool(produced) or bool(trace.raw_result.get("acceptance_met"))


@check(id="CHK-guardrail-fp-budget", failure_mode_id="FM-005", tier="A")
def guardrail_fp_budget(trace: Trace) -> CheckResult:
    """Fail when guardrail fails fire on a run that otherwise met acceptance."""
    cid = "CHK-guardrail-fp-budget"
    fm = "FM-005"

    guard_spans = trace.spans_of("guardrail_check")
    if not guard_spans:
        return na(cid, trace, "no guardrail_check spans", failure_mode_id=fm)

    if not _acceptance_met(trace):
        return na(
            cid,
            trace,
            "run did not meet acceptance criteria; FP budget not applicable",
            failure_mode_id=fm,
        )

    fails = [
        s
        for s in guard_spans
        if str(s.payload.get("outcome") or s.payload.get("status") or "").lower()
        in {"fail", "failed", "violation"}
    ]
    if fails:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_span_ids=[s.span_id for s in fails],
            evidence_text=f"{len(fails)} guardrail fail(s) on otherwise-accepted run",
            detail={"fail_count": len(fails)},
        )
    return passed(
        cid,
        trace,
        failure_mode_id=fm,
        evidence_text="no guardrail false positives on accepted run",
    )
