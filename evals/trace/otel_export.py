"""Export an ai-team :class:`Trace` as OTLP JSON, without the OpenTelemetry SDK.

This is a projection of the harness record, not a second telemetry system: the same trace
always gives the same bytes. Every span carries both the OpenInference names (read by Phoenix)
and the OTel GenAI names (read by Aspire and the cloud consoles), plus ``ai_team.span.type``
so :func:`evals.trace.otel_import.import_otlp` can read our own exports back without loss.

Spec: ``.kiro/specs/otel-observability/`` (R1, R2.3, design §3–§5).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from evals.trace.models import Span, Trace

SCHEMA_URL = "https://opentelemetry.io/schemas/1.42.0"
SCOPE_NAME = "ai_team.evals.otel_export"
SCOPE_VERSION = "1"
PROJECT_NAME = "ai-team"
CONTENT_LIMIT = 2048
BATCH_SIZE = 512

# Same list as ai_team/ui/artifacts/service.py::_SENSITIVE_SUBSTR (a unit test keeps them equal).
SENSITIVE_SUBSTR = (".env", "credentials", "secrets", "id_rsa", ".pem")

# Payload keys whose values are content: left out unless with_content=True.
CONTENT_KEYS = frozenset(
    {
        "summary",
        "evidence",
        "issues",
        "messages",
        "input",
        "output",
        "content",
        "prompt",
        "response",
        "args",
        "arguments",
        "detail",
        "result_text",
        "error_text",
    }
)

# ai-team span type -> (GenAI operation, OpenInference span kind). One table, read by tests.
SPAN_SPECS: dict[str, tuple[str | None, str]] = {
    "llm_call": ("chat", "LLM"),
    "tool_use": ("execute_tool", "TOOL"),
    "tool_result": ("execute_tool", "TOOL"),
    "agent": ("invoke_agent", "AGENT"),
    "subagent_start": ("invoke_agent", "AGENT"),
    "subagent_stop": ("invoke_agent", "AGENT"),
    "session_start": ("invoke_agent", "AGENT"),
    "session_end": ("invoke_agent", "AGENT"),
    "guardrail_check": (None, "GUARDRAIL"),
    "qa_verdict": (None, "EVALUATOR"),
    "qa_disagreement": (None, "EVALUATOR"),
    "regression_check": (None, "EVALUATOR"),
}
DEFAULT_SPEC: tuple[str | None, str] = (None, "CHAIN")

# Start/end pairs that become one span with a duration (design §3.2).
MERGE_PAIRS: dict[str, str] = {
    "tool_use": "tool_result",
    "phase_start": "phase_end",
    "subagent_start": "subagent_stop",
    "session_start": "session_end",
}

STATUS_OK, STATUS_ERROR = 1, 2
SPAN_KIND_INTERNAL = 1


@dataclass
class _Unit:
    """One exported span: one ai-team span, or a merged start/end pair."""

    members: list[Span]
    span_id: str = ""
    parent_id: str = ""

    @property
    def first(self) -> Span:
        return self.members[0]

    @property
    def types(self) -> list[str]:
        return [m.type for m in self.members]

    @property
    def start_ns(self) -> int:
        return _ns(self.first.t_start)

    @property
    def end_ns(self) -> int:
        last = self.members[-1]
        end = last.t_end if len(self.members) == 1 and last.t_end else last.t_start
        return max(_ns(end), self.start_ns)


@dataclass(frozen=True)
class ExportOptions:
    """What to include. Content is off by default (R1.3)."""

    with_content: bool = False
    backend: str | None = None
    run_id: str | None = None
    model_tier: str | None = None
    batch_size: int = BATCH_SIZE
    extra_resource: dict[str, str] = field(default_factory=dict)


def _ns(value: datetime) -> int:
    return int(value.timestamp() * 1_000_000_000)


def _hex(*parts: object, length: int) -> str:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return digest[:length]


def _tool_name(span: Span) -> str:
    return str(span.payload.get("tool") or span.payload.get("tool_name") or "")


def _pair_key(span: Span) -> tuple[str, ...]:
    """What a start span and its end span must share (design §6: there is no call id)."""
    if span.type in ("tool_use", "tool_result"):
        return (
            _tool_name(span),
            span.agent_role or "",
            span.phase or "",
            str(span.payload.get("run_id") or ""),
        )
    if span.type in ("phase_start", "phase_end"):
        return (str(span.payload.get("phase") or span.phase or ""),)
    if span.type in ("session_start", "session_end"):
        return (str(span.payload.get("session_id") or ""),)
    return (span.agent_role or "",)


def merge_units(spans: list[Span]) -> list[_Unit]:
    """Pair start/end spans (design §3.2). Unpaired spans are kept on their own."""
    ends = set(MERGE_PAIRS.values())
    # Same timestamp: a start sorts before its end, whatever the builder's ids say.
    ordered = sorted(spans, key=lambda s: (_ns(s.t_start), s.type in ends, s.span_id))
    used: set[int] = set()
    units: list[_Unit] = []
    for i, span in enumerate(ordered):
        if i in used:
            continue
        used.add(i)
        end_type = MERGE_PAIRS.get(span.type)
        partner = None
        if end_type is not None:
            key = _pair_key(span)
            for j in range(i + 1, len(ordered)):
                cand = ordered[j]
                if j not in used and cand.type == end_type and _pair_key(cand) == key:
                    partner = j
                    break
        if partner is None:
            units.append(_Unit(members=[span]))
        else:
            used.add(partner)
            units.append(_Unit(members=[span, ordered[partner]]))
    return units


def _unit_name(unit: _Unit) -> str:
    span = unit.first
    if span.type in ("tool_use", "tool_result"):
        return f"execute_tool {_tool_name(span)}".strip()
    if span.type == "llm_call":
        return f"chat {span.payload.get('model') or ''}".strip()
    if span.type in ("phase_start", "phase_end"):
        return f"phase {span.payload.get('phase') or span.phase or ''}".strip()
    if SPAN_SPECS.get(span.type, DEFAULT_SPEC)[1] == "AGENT":
        return f"invoke_agent {span.agent_role or ''}".strip()
    return span.type


def _assign_ids(trace_hex: str, units: list[_Unit]) -> None:
    """Span ids from content that doesn't move (R2.3), with an occurrence counter."""
    seen: dict[str, int] = {}
    for unit in units:
        span = unit.first
        base = "|".join(
            [
                ",".join(unit.types),
                span.agent_role or "",
                span.phase or "",
                str(unit.start_ns),
                _unit_name(unit),
            ]
        )
        n = seen.get(base, 0)
        seen[base] = n + 1
        unit.span_id = _hex(trace_hex, base, n, length=16)


def _assign_parents(units: list[_Unit], root_id: str) -> None:
    """Phase spans under the run; agents under their phase; the rest under agent or phase."""
    phases = [u for u in units if u.first.type in ("phase_start", "phase_end")]
    agents = [u for u in units if SPAN_SPECS.get(u.first.type, DEFAULT_SPEC)[1] == "AGENT"]

    def phase_of(unit: _Unit) -> _Unit | None:
        name = unit.first.phase
        for p in phases:
            pname = p.first.payload.get("phase") or p.first.phase
            if name and pname == name and p.start_ns <= unit.start_ns <= p.end_ns and p is not unit:
                return p
        return None

    for unit in units:
        if unit in phases:
            unit.parent_id = root_id
            continue
        parent = phase_of(unit)
        if unit not in agents:
            for a in agents:
                role_match = a.first.agent_role and a.first.agent_role == unit.first.agent_role
                if role_match and a.start_ns <= unit.start_ns <= a.end_ns:
                    parent = a
                    break
        unit.parent_id = parent.span_id if parent is not None else root_id


def _value(v: Any) -> dict[str, Any]:
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, list):
        return {"arrayValue": {"values": [_value(x) for x in v]}}
    return {"stringValue": str(v)}


def _kv(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"key": k, "value": _value(attrs[k])} for k in sorted(attrs) if attrs[k] is not None]


def _redacted(text: str) -> bool:
    low = text.lower()
    return any(s in low for s in SENSITIVE_SUBSTR)


def _content(key: str, raw: Any, with_content: bool) -> dict[str, Any]:
    """Content attributes: hash and size when off; text cut to 2 KB when on (R1.3)."""
    text = raw if isinstance(raw, str) else json.dumps(raw, sort_keys=True, default=str)
    if _redacted(text):
        return {f"ai_team.{key}": "[redacted]"}
    data = text.encode("utf-8")
    out: dict[str, Any] = {
        f"ai_team.{key}.bytes": len(data),
        f"ai_team.{key}.sha256": hashlib.sha256(data).hexdigest(),
    }
    if with_content:
        out[f"ai_team.{key}"] = data[:CONTENT_LIMIT].decode("utf-8", "ignore")
        if len(data) > CONTENT_LIMIT:
            out["ai_team.truncated"] = True
    return out


def _payload_attrs(span: Span, with_content: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in sorted(span.payload):
        raw = span.payload[key]
        if raw is None:
            continue
        if key in CONTENT_KEYS:
            out.update(_content(key, raw, with_content))
        elif isinstance(raw, bool | int | float):
            out[f"ai_team.payload.{key}"] = raw
        else:
            text = raw if isinstance(raw, str) else json.dumps(raw, sort_keys=True, default=str)
            out[f"ai_team.payload.{key}"] = (
                "[redacted]" if _redacted(text) else text[:CONTENT_LIMIT]
            )
    return out


def _llm_attrs(span: Span, model_ids: dict[str, str]) -> dict[str, Any]:
    raw_usage = span.payload.get("usage")
    usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
    tin = usage.get("input_tokens", usage.get("prompt_tokens"))
    tout = usage.get("output_tokens", usage.get("completion_tokens"))
    model = span.payload.get("model") or (
        model_ids.get(span.agent_role or "") if model_ids else None
    )
    if not model and len(model_ids) == 1:
        model = next(iter(model_ids.values()))
    out: dict[str, Any] = {
        "llm.model_name": model,
        "gen_ai.request.model": model,
        "llm.token_count.prompt": tin,
        "gen_ai.usage.input_tokens": tin,
        "llm.token_count.completion": tout,
        "gen_ai.usage.output_tokens": tout,
        "ai_team.cost_usd": span.payload.get("cost_usd"),
    }
    if tin is None and tout is None:
        out["ai_team.tokens_missing"] = True
    return out


def _unit_attrs(unit: _Unit, model_ids: dict[str, str], opts: ExportOptions) -> dict[str, Any]:
    span = unit.first
    op, kind = SPAN_SPECS.get(span.type, DEFAULT_SPEC)
    attrs: dict[str, Any] = {
        "openinference.span.kind": kind,
        "gen_ai.operation.name": op,
        "ai_team.span.type": span.type,
        "ai_team.role": span.agent_role,
        "ai_team.phase": span.phase,
    }
    if len(unit.members) > 1:
        attrs["ai_team.span.merged"] = unit.types
    elif MERGE_PAIRS.get(span.type) or span.type in MERGE_PAIRS.values():
        attrs["ai_team.unpaired"] = True
    if kind == "TOOL":
        name = _tool_name(span)
        attrs.update({"tool.name": name, "gen_ai.tool.name": name})
    if kind == "AGENT":
        attrs.update({"agent.name": span.agent_role, "gen_ai.agent.name": span.agent_role})
    if span.type == "llm_call":
        attrs.update(_llm_attrs(span, model_ids))
    for member in unit.members:
        attrs.update(_payload_attrs(member, opts.with_content))
    if opts.with_content and kind == "TOOL":
        summary = unit.members[-1].payload.get("summary")
        if isinstance(summary, str) and not _redacted(summary):
            attrs["output.value"] = summary[:CONTENT_LIMIT]
    return attrs


def _is_error(unit: _Unit) -> bool:
    return any(m.payload.get("ok") is False or m.type == "error" for m in unit.members)


def _otlp_span(trace_hex: str, unit: _Unit, attrs: dict[str, Any]) -> dict[str, Any]:
    span: dict[str, Any] = {
        "traceId": trace_hex,
        "spanId": unit.span_id,
        "parentSpanId": unit.parent_id,
        "name": _unit_name(unit),
        "kind": SPAN_KIND_INTERNAL,
        "startTimeUnixNano": str(unit.start_ns),
        "endTimeUnixNano": str(unit.end_ns),
        "attributes": _kv(attrs),
    }
    if _is_error(unit):
        span["status"] = {"code": STATUS_ERROR}
    return span


def _resource(trace: Trace, opts: ExportOptions) -> dict[str, Any]:
    backend = opts.backend or trace.backend
    attrs = {
        "service.name": f"ai-team.{backend}",
        "openinference.project.name": PROJECT_NAME,
        "ai_team.backend": backend,
        "ai_team.run_id": opts.run_id or trace.trace_id,
        "ai_team.source": "harness",
        "ai_team.model_tier": opts.model_tier or "unknown",
        **opts.extra_resource,
    }
    return {"attributes": _kv(attrs)}


def _root_span(trace: Trace, trace_hex: str, root_id: str, units: list[_Unit]) -> dict[str, Any]:
    start = min([u.start_ns for u in units] + [_ns(trace.started_at)])
    ends = [u.end_ns for u in units] + ([_ns(trace.ended_at)] if trace.ended_at else [])
    attrs = {
        "openinference.span.kind": "CHAIN",
        "ai_team.span.type": "run",
        "ai_team.status": trace.status,
        "ai_team.scenario_id": trace.scenario_id,
    }
    span = {
        "traceId": trace_hex,
        "spanId": root_id,
        "parentSpanId": "",
        "name": "run",
        "kind": SPAN_KIND_INTERNAL,
        "startTimeUnixNano": str(start),
        "endTimeUnixNano": str(max(ends + [start])),
        "attributes": _kv(attrs),
    }
    if trace.status in ("failed", "killed", "budget_abort"):
        span["status"] = {"code": STATUS_ERROR}
    return span


def _trace_key(trace: Trace, opts: ExportOptions) -> str:
    """What the OTel trace id is derived from.

    Not ``trace.trace_id``: ``make_trace_id`` adds a random suffix on every build, so it would
    give a new OTel trace for every re-export. The run id is stable.
    """
    if opts.run_id:
        return f"run|{opts.run_id}"
    return f"trace|{trace.scenario_id}|{trace.backend}|{_ns(trace.started_at)}"


def export_spans(trace: Trace, opts: ExportOptions | None = None) -> list[dict[str, Any]]:
    """All OTLP span objects for a trace, root first, in a stable order."""
    opts = opts or ExportOptions()
    trace_hex = _hex(_trace_key(trace, opts), length=32)
    root_id = _hex(trace_hex, "run", length=16)
    units = merge_units(trace.spans)
    _assign_ids(trace_hex, units)
    _assign_parents(units, root_id)
    model_ids = dict(trace.provenance.model_ids or {})
    spans = [_root_span(trace, trace_hex, root_id, units)]
    spans += [_otlp_span(trace_hex, u, _unit_attrs(u, model_ids, opts)) for u in units]
    return spans


def export_requests(trace: Trace, opts: ExportOptions | None = None) -> list[dict[str, Any]]:
    """OTLP ``ExportTraceServiceRequest`` bodies, at most ``batch_size`` spans each."""
    opts = opts or ExportOptions()
    spans = export_spans(trace, opts)
    resource = _resource(trace, opts)
    scope = {"name": SCOPE_NAME, "version": SCOPE_VERSION}
    size = max(1, opts.batch_size)
    return [
        {
            "resourceSpans": [
                {
                    "resource": resource,
                    "schemaUrl": SCHEMA_URL,
                    "scopeSpans": [
                        {"scope": scope, "schemaUrl": SCHEMA_URL, "spans": spans[i : i + size]}
                    ],
                }
            ]
        }
        for i in range(0, len(spans), size)
    ]


def to_jsonl(requests: list[dict[str, Any]]) -> str:
    """One request per line, sorted keys, no spaces: the same trace gives the same bytes."""
    return "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in requests)
