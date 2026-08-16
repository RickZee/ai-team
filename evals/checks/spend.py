"""Spend ceiling check: FM-007."""

from __future__ import annotations

from evals.checks._helpers import scenario_config
from evals.checks.base import CheckResult, failed, na, passed
from evals.checks.registry import check
from evals.trace.models import Trace


@check(id="CHK-spend-ceiling", failure_mode_id="FM-007", tier="A")
def spend_ceiling(trace: Trace) -> CheckResult:
    """Fail when cost exceeds scenario budget or spend guard failed to abort."""
    cid = "CHK-spend-ceiling"
    fm = "FM-007"

    cfg = scenario_config(trace)
    budget = cfg.get("budget_usd_max")
    if budget is None and trace.cost.usd is None and not trace.spans_of("spend_event"):
        return na(cid, trace, "no cost or spend_event data", failure_mode_id=fm)

    budget_f = float(budget) if budget is not None else None
    offenders: list[str] = []
    detail: dict[str, object] = {}

    if budget_f is not None and trace.cost.usd is not None and trace.cost.usd > budget_f:
        detail["cost_usd"] = trace.cost.usd
        detail["budget_usd_max"] = budget_f
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_text=f"cost.usd={trace.cost.usd} > budget_usd_max={budget_f}",
            detail=detail,
        )

    # spend_event showing past-ceiling without abort
    for s in trace.spans_of("spend_event"):
        cumulative = s.payload.get("cumulative_usd")
        ceiling = s.payload.get("ceiling_usd", budget_f)
        aborted = s.payload.get("aborted") or s.payload.get("guard_aborted")
        if cumulative is not None and ceiling is not None:
            try:
                if float(cumulative) > float(ceiling) and not aborted:
                    offenders.append(s.span_id)
            except (TypeError, ValueError):
                continue

    if offenders:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_span_ids=offenders,
            evidence_text="spend_event past ceiling without abort",
            detail={"offender_span_ids": offenders},
        )

    if budget_f is None and not trace.spans_of("spend_event"):
        return na(cid, trace, "no budget configured and no spend_event", failure_mode_id=fm)

    return passed(
        cid,
        trace,
        failure_mode_id=fm,
        evidence_text="spend within ceiling",
        detail={"cost_usd": trace.cost.usd, "budget_usd_max": budget_f},
    )
