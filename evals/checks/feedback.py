"""Feedback-layer checks: FM-013 lesson effectiveness."""

from __future__ import annotations

from evals.checks.base import CheckResult, failed, na, passed
from evals.checks.registry import check
from evals.trace.models import Trace


@check(id="CHK-lesson-effectiveness", failure_mode_id="FM-013", tier="A")
def lesson_effectiveness(trace: Trace) -> CheckResult:
    """Fail when a lesson is ineffective and not escalated."""
    cid = "CHK-lesson-effectiveness"
    fm = "FM-013"
    lessons = trace.raw_result.get("lessons") if isinstance(trace.raw_result, dict) else None
    if not lessons:
        return na(cid, trace, "no lessons in trace.raw_result", failure_mode_id=fm)
    if not isinstance(lessons, list):
        return na(cid, trace, "lessons payload is not a list", failure_mode_id=fm)

    bad: list[str] = []
    for row in lessons:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "")
        lid = str(row.get("lesson_id") or row.get("id") or "")
        if status == "ineffective":
            bad.append(lid)
    if bad:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_text=f"ineffective lessons not escalated: {bad}",
            detail={"lesson_ids": bad},
        )
    return passed(cid, trace, failure_mode_id=fm, evidence_text="lessons effective or escalated")
