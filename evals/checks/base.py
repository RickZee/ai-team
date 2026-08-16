"""Check protocol and result helpers (R5.1)."""

from __future__ import annotations

from typing import Any, ClassVar, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from evals.trace.models import Trace

CheckOutcome = Literal["pass", "fail", "not_applicable", "error"]
CheckTier = Literal["A", "B", "C"]


class CheckResult(BaseModel):
    """Outcome of one deterministic check against one trace."""

    check_id: str
    failure_mode_id: str | None
    trace_id: str
    outcome: CheckOutcome
    evidence_span_ids: list[str] = Field(default_factory=list)
    evidence_text: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class Check(Protocol):
    """Deterministic, code-only predicate over a Trace."""

    id: ClassVar[str]
    failure_mode_id: ClassVar[str | None]
    tier: ClassVar[CheckTier]

    def run(self, trace: Trace) -> CheckResult:
        """Evaluate *trace* and return a structured result."""
        ...


def passed(
    check_id: str,
    trace: Trace,
    *,
    failure_mode_id: str | None = None,
    evidence_span_ids: list[str] | None = None,
    evidence_text: str = "",
    detail: dict[str, Any] | None = None,
) -> CheckResult:
    """Build a ``pass`` result."""
    return CheckResult(
        check_id=check_id,
        failure_mode_id=failure_mode_id,
        trace_id=trace.trace_id,
        outcome="pass",
        evidence_span_ids=evidence_span_ids or [],
        evidence_text=evidence_text,
        detail=detail or {},
    )


def failed(
    check_id: str,
    trace: Trace,
    *,
    failure_mode_id: str | None = None,
    evidence_span_ids: list[str] | None = None,
    evidence_text: str = "",
    detail: dict[str, Any] | None = None,
) -> CheckResult:
    """Build a ``fail`` result."""
    return CheckResult(
        check_id=check_id,
        failure_mode_id=failure_mode_id,
        trace_id=trace.trace_id,
        outcome="fail",
        evidence_span_ids=evidence_span_ids or [],
        evidence_text=evidence_text,
        detail=detail or {},
    )


def na(
    check_id: str,
    trace: Trace,
    reason: str,
    *,
    failure_mode_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> CheckResult:
    """Build a ``not_applicable`` result (excluded from aggregation denominators)."""
    return CheckResult(
        check_id=check_id,
        failure_mode_id=failure_mode_id,
        trace_id=trace.trace_id,
        outcome="not_applicable",
        evidence_text=reason,
        detail=detail or {},
    )
