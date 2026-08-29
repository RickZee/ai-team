"""Metric source agreement check: FM-008."""

from __future__ import annotations

import contextlib

from evals.checks._helpers import scenario_config
from evals.checks.base import CheckResult, failed, na, passed
from evals.checks.registry import check
from evals.trace.models import Trace


@check(id="CHK-metric-source-agreement", failure_mode_id="FM-008", tier="A")
def metric_source_agreement(trace: Trace) -> CheckResult:
    """Fail when artifact-derived metrics disagree with event-derived values.

    Defaults: exact match for file counts; 5% relative tolerance for cost.
    Event-derived values come from ``raw_result.event_metrics`` (or equivalent
    payload fields) when backends emit them.
    """
    cid = "CHK-metric-source-agreement"
    fm = "FM-008"

    events = trace.raw_result.get("event_metrics")
    if not isinstance(events, dict):
        return na(
            cid,
            trace,
            "no event_metrics on trace for comparison",
            failure_mode_id=fm,
        )

    cfg = scenario_config(trace)
    cost_tol = float(cfg.get("metric_cost_tolerance", 0.05))

    artifact_files = len(trace.files())
    event_files = events.get("file_count")
    artifact_cost = trace.cost.usd
    event_cost = events.get("cost_usd")

    # Disk receipt is the source of truth when present (FM-008 / R15.5).
    receipt = trace.raw_result.get("receipt")
    if isinstance(receipt, dict):
        rec_files = receipt.get("file_count")
        rec_cost = receipt.get("cost_usd")
        if rec_files is not None:
            with contextlib.suppress(TypeError, ValueError):
                artifact_files = int(rec_files)
        if rec_cost is not None:
            with contextlib.suppress(TypeError, ValueError):
                artifact_cost = float(rec_cost)

    disagreements: list[str] = []
    detail: dict[str, object] = {
        "artifact_file_count": artifact_files,
        "event_file_count": event_files,
        "artifact_cost_usd": artifact_cost,
        "event_cost_usd": event_cost,
    }

    if event_files is not None:
        try:
            if int(event_files) != artifact_files:
                disagreements.append(f"file_count artifact={artifact_files} event={event_files}")
        except (TypeError, ValueError):
            disagreements.append(f"file_count event unparseable: {event_files!r}")

    if event_cost is not None and artifact_cost is not None:
        try:
            ev = float(event_cost)
            if artifact_cost == 0 and ev == 0:
                pass
            else:
                denom = max(abs(artifact_cost), abs(ev), 1e-9)
                rel = abs(artifact_cost - ev) / denom
                if rel > cost_tol:
                    disagreements.append(
                        f"cost_usd artifact={artifact_cost} event={ev} rel={rel:.4f}"
                    )
        except (TypeError, ValueError):
            disagreements.append(f"cost_usd event unparseable: {event_cost!r}")

    if event_files is None and event_cost is None:
        return na(cid, trace, "event_metrics lacks file_count and cost_usd", failure_mode_id=fm)

    if disagreements:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_text="; ".join(disagreements),
            detail=detail,
        )
    return passed(cid, trace, failure_mode_id=fm, evidence_text="metrics agree", detail=detail)
