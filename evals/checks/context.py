"""Context-layer checks: FM-011 constraint survival, FM-015 context anxiety."""

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


_DEFAULT_PRESSURE = 0.75
_EXPLAINED = frozenset({"spend_event", "error"})


def _unsatisfied_count(trace: Trace) -> int | None:
    raw = trace.raw_result.get("acceptance_unsatisfied")
    if isinstance(raw, int):
        return raw
    snaps = trace.raw_result.get("acceptance_snapshots")
    if isinstance(snaps, list) and snaps:
        last = snaps[-1]
        items = last.get("snapshot") if isinstance(last, dict) else None
        if isinstance(items, list):
            return sum(1 for i in items if isinstance(i, dict) and i.get("passes") is not True)
    return None


@check(id="CHK-premature-termination", failure_mode_id="FM-015", tier="A")
def premature_termination(trace: Trace) -> CheckResult:
    """Fail when a run wraps up ok under high context pressure with work remaining."""
    cid = "CHK-premature-termination"
    fm = "FM-015"
    ends = [s for s in trace.spans if s.type in ("phase_end", "session_end")]
    if not ends:
        return na(cid, trace, "no phase_end/session_end spans", failure_mode_id=fm)
    last = ends[-1]
    pressure = last.payload.get("context_pressure")
    if pressure is None:
        return na(
            cid,
            trace,
            "inconclusive: context_pressure is None",
            failure_mode_id=fm,
        )
    try:
        pressure_f = float(pressure)
    except (TypeError, ValueError):
        return na(cid, trace, "inconclusive: context_pressure is None", failure_mode_id=fm)

    threshold = float(trace.raw_result.get("context_pressure_threshold") or _DEFAULT_PRESSURE)
    end_status = str(last.payload.get("status") or trace.status or "").lower()
    ok_status = end_status in {"ok", "complete", "success", "done"}

    trailing = trace.spans[-8:]
    explained = False
    for s in trailing:
        if s.type in _EXPLAINED:
            explained = True
        payload = s.payload
        if payload.get("watchdog") or payload.get("killed") or payload.get("max_turns"):
            explained = True
        if s.type == "spend_event":
            explained = True
    if trace.status in {"killed", "budget_abort"}:
        explained = True
    if last.payload.get("max_turns") or last.payload.get("watchdog"):
        explained = True

    unsatisfied = _unsatisfied_count(trace)
    if unsatisfied is None:
        return na(cid, trace, "inconclusive: no acceptance state", failure_mode_id=fm)

    if ok_status and unsatisfied >= 1 and not explained and pressure_f >= threshold:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_span_ids=[last.span_id],
            evidence_text=(
                f"ended {end_status} with {unsatisfied} unsatisfied items "
                f"at context_pressure={pressure_f:.2f}"
            ),
        )
    return passed(
        cid,
        trace,
        failure_mode_id=fm,
        evidence_text="termination explained or pressure below threshold",
    )
