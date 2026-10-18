"""Small trace factory shared by the OTel export tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from evals.provenance import Provenance
from evals.trace.models import CostRecord, Span, Trace

T0 = datetime(2026, 10, 18, 12, 0, 0, tzinfo=UTC)


def at(seconds: float) -> datetime:
    """A timestamp ``seconds`` after T0."""
    return T0 + timedelta(seconds=seconds)


def span(
    kind: str,
    t: float,
    *,
    role: str | None = None,
    phase: str | None = None,
    sid: str | None = None,
    **payload: Any,
) -> Span:
    """A zero-length span, as the parsers produce them."""
    return Span(
        span_id=sid or f"s_{kind}_{t}",
        type=kind,  # type: ignore[arg-type]
        t_start=at(t),
        t_end=at(t),
        agent_role=role,
        phase=phase,
        payload=dict(payload),
    )


def make_trace(
    spans: list[Span], *, trace_id: str = "thin__langgraph__x__abcd", **kw: Any
) -> Trace:
    """A minimal valid Trace around ``spans``."""
    return Trace(
        trace_id=trace_id,
        scenario_id=kw.get("scenario_id", "thin-slice"),
        backend=kw.get("backend", "langgraph"),
        status=kw.get("status", "complete"),
        started_at=T0,
        ended_at=at(600),
        spans=spans,
        artifacts=[],
        cost=CostRecord(usd=None, input_tokens=None, output_tokens=None, source="unknown"),
        provenance=Provenance(
            git_sha="0" * 40,
            git_dirty=False,
            python_version="3.12",
            platform="test",
            harness_version="0",
            taxonomy_version="0",
            pricing_table_version="0",
            model_ids=kw.get("model_ids", {}),
        ),
    )


def attrs(otlp_span: dict[str, Any]) -> dict[str, Any]:
    """Flatten an exported span's attribute list for assertions."""
    out: dict[str, Any] = {}
    for item in otlp_span["attributes"]:
        ((kind, value),) = item["value"].items()
        if kind == "arrayValue":
            value = [next(iter(v.values())) for v in value["values"]]
        elif kind == "intValue":
            value = int(value)
        out[item["key"]] = value
    return out


def tool_pair(t: float, tool: str, role: str = "dev", phase: str = "development", **result: Any):
    """A tool_use and its tool_result one second later, as ToolBus writes them."""
    base = {"tool": tool, "tool_name": tool, "run_id": "r1"}
    return [
        span("tool_use", t, role=role, phase=phase, sid=f"u{t}", **base),
        span(
            "tool_result",
            t + 1,
            role=role,
            phase=phase,
            sid=f"r{t}",
            **base,
            ok=result.pop("ok", True),
            **result,
        ),
    ]
