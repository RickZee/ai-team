"""Trajectory checks: FM-001, FM-002, FM-003."""

from __future__ import annotations

from datetime import datetime

from evals.checks._helpers import (
    has_fenced_code,
    is_write_tool,
    no_audit_log,
    scenario_config,
)
from evals.checks.base import CheckResult, failed, na, passed
from evals.checks.registry import check
from evals.trace.models import Trace

_DEV_PHASES = frozenset({"development", "testing", "qa"})


@check(id="CHK-tool-call-emitted", failure_mode_id="FM-001", tier="A")
def tool_call_emitted(trace: Trace) -> CheckResult:
    """Fail when a development phase completes with no file-writing tool use.

    Also fails when fenced code appears in phase output with no corresponding
    source/test artifact. Returns ``not_applicable`` when no development phase
    ran, or when the backend emitted no tool-level audit log.
    """
    cid = "CHK-tool-call-emitted"
    fm = "FM-001"

    dev_ends = [s for s in trace.spans_of("phase_end") if s.phase in _DEV_PHASES]
    if not dev_ends:
        return na(cid, trace, "no development phase in trace", failure_mode_id=fm)

    if not trace.spans_of("tool_use") and no_audit_log(trace):
        return na(cid, trace, "backend emits no tool-level audit", failure_mode_id=fm)

    offenders: list[str] = []
    for phase in dev_ends:
        writes = [
            s
            for s in trace.spans_of("tool_use")
            if s.phase == phase.phase and is_write_tool(s.payload)
        ]
        produced = [a for a in trace.files() if a.kind in {"source", "test"}]
        output = str(
            phase.payload.get("output")
            or phase.payload.get("message")
            or phase.payload.get("content")
            or ""
        )
        if not writes and (has_fenced_code(output) or not produced):
            offenders.append(phase.span_id)

    if offenders:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_span_ids=offenders,
            evidence_text="development phase completed without file-writing tool calls",
            detail={"offender_span_ids": offenders},
        )
    return passed(cid, trace, failure_mode_id=fm, evidence_text="tool writes observed")


@check(id="CHK-phase-repeat-bounded", failure_mode_id="FM-002", tier="A")
def phase_repeat_bounded(trace: Trace) -> CheckResult:
    """Fail when any ``(phase, agent_role)`` exceeds ``max_phase_repeats``."""
    cid = "CHK-phase-repeat-bounded"
    fm = "FM-002"

    starts = trace.spans_of("phase_start")
    if not starts:
        return na(cid, trace, "no phase_start spans", failure_mode_id=fm)

    cfg = scenario_config(trace)
    max_repeats = int(cfg.get("max_phase_repeats", 4))
    counts = trace.phase_repeats()
    if not counts:
        return na(cid, trace, "no countable phase_start events", failure_mode_id=fm)

    offenders = {k: n for k, n in counts.items() if n > max_repeats}
    if offenders:
        # Map keys back to representative span ids
        span_ids: list[str] = []
        for s in starts:
            key = (s.phase or "", s.agent_role)
            if key in offenders or ((s.phase, s.agent_role) in offenders):
                span_ids.append(s.span_id)
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_span_ids=span_ids[:20],
            evidence_text=f"phase repeats exceeded max_phase_repeats={max_repeats}",
            detail={
                "max_phase_repeats": max_repeats,
                "offenders": {f"{p}|{a}": n for (p, a), n in offenders.items()},
            },
        )
    return passed(
        cid,
        trace,
        failure_mode_id=fm,
        evidence_text=f"all phase repeats ≤ {max_repeats}",
        detail={"counts": {f"{p}|{a}": n for (p, a), n in counts.items()}},
    )


@check(id="CHK-listener-self-trigger", failure_mode_id="FM-002", tier="A")
def listener_self_trigger(trace: Trace) -> CheckResult:
    """Fail when a CrewAI Flow method ``@listen``s to its own name.

    Introspects live flow wiring via :mod:`ai_team.core.flow_wiring`. Fixture
    traces may inject ``raw_result.listener_self_triggers`` for fail cases
    without mutating production wiring. Non-crewai backends return
    ``not_applicable``.
    """
    cid = "CHK-listener-self-trigger"
    fm = "FM-002"

    injected = trace.raw_result.get("listener_self_triggers")
    if injected is not None:
        offenders = [str(x) for x in injected]
    elif trace.backend != "crewai":
        return na(
            cid,
            trace,
            "listener self-trigger check applies to crewai flows only",
            failure_mode_id=fm,
        )
    elif trace.raw_result.get("skip_listener_check"):
        return na(cid, trace, "listener check skipped by fixture", failure_mode_id=fm)
    else:
        offenders = _cached_self_triggering_listeners()

    if offenders:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_text=f"self-triggering listeners: {offenders}",
            detail={"offenders": offenders},
        )
    return passed(cid, trace, failure_mode_id=fm, evidence_text="no self-triggering listeners")


_SELF_TRIGGER_CACHE: list[str] | None = None


def _cached_self_triggering_listeners() -> list[str]:
    """Memoize flow introspection — class wiring is process-static (R5.5)."""
    global _SELF_TRIGGER_CACHE
    if _SELF_TRIGGER_CACHE is None:
        from ai_team.core.flow_wiring import (
            get_registered_flow_class,
            self_triggering_listeners,
        )

        cls = get_registered_flow_class()
        if cls is None:
            return []
        _SELF_TRIGGER_CACHE = list(self_triggering_listeners(cls))
    return _SELF_TRIGGER_CACHE


@check(id="CHK-interrupt-latency", failure_mode_id="FM-003", tier="A")
def interrupt_latency(trace: Trace) -> CheckResult:
    """Fail when human_interrupt → surface latency exceeds the configured ceiling."""
    cid = "CHK-interrupt-latency"
    fm = "FM-003"

    interrupts = trace.spans_of("human_interrupt")
    if not interrupts:
        return na(cid, trace, "no human_interrupt spans", failure_mode_id=fm)

    cfg = scenario_config(trace)
    max_s = float(cfg.get("max_interrupt_latency_s", 60.0))

    offenders: list[str] = []
    details: list[dict[str, float | str]] = []
    for span in interrupts:
        surfaced_at = _surfaced_at(span, trace)
        if surfaced_at is None:
            # Incomplete interrupt with no surface event — treat end or trace end
            if span.t_end is not None:
                surfaced_at = span.t_end
            elif trace.ended_at is not None:
                surfaced_at = trace.ended_at
            else:
                continue
        elapsed = (surfaced_at - span.t_start).total_seconds()
        if elapsed > max_s:
            offenders.append(span.span_id)
            details.append(
                {
                    "span_id": span.span_id,
                    "elapsed_s": elapsed,
                    "max_interrupt_latency_s": max_s,
                }
            )

    if not details and not offenders:
        # Interrupts present but none measurable → pass if all within bound via duration
        for span in interrupts:
            if span.duration_s is not None and span.duration_s > max_s:
                offenders.append(span.span_id)
                details.append(
                    {
                        "span_id": span.span_id,
                        "elapsed_s": float(span.duration_s),
                        "max_interrupt_latency_s": max_s,
                    }
                )

    if offenders:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_span_ids=offenders,
            evidence_text=f"interrupt latency exceeded {max_s}s",
            detail={"offenders": details},
        )
    return passed(cid, trace, failure_mode_id=fm, evidence_text=f"interrupt latency ≤ {max_s}s")


def _surfaced_at(interrupt_span: object, trace: Trace) -> datetime | None:
    """Resolve when an interrupt became visible to the operator."""
    payload = getattr(interrupt_span, "payload", {}) or {}
    raw = payload.get("surfaced_at") or payload.get("acknowledged_at")
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    # Explicit surface span linked by parent or payload interrupt_span_id
    sid = getattr(interrupt_span, "span_id", None)
    for s in trace.spans:
        if s.payload.get("kind") == "interrupt_surfaced" and (
            s.parent_span_id == sid or s.payload.get("interrupt_span_id") == sid
        ):
            return s.t_start
    return None
