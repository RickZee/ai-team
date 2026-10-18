"""Map OpenTelemetry spans onto ai-team span kinds.

Framework spans (Strands, Agent Framework, cloud consoles) go through one table; unknown
names become ``other`` and are counted. Spans written by :mod:`evals.trace.otel_export` carry
``ai_team.span.type`` (and ``ai_team.span.merged`` for start/end pairs) and are read back
exactly, so ``import_otlp(export(trace))`` gives back the trace's span types, counts, roles,
phases and start times (otel-observability R3).
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.trace.models import Span, Trace

# (gen_ai.operation.name or span name) → ai-team span type.
# "llm" in the spec is ``llm_call`` in this repo's span vocabulary.
SPAN_KIND_MAP: dict[str, str] = {
    "chat": "llm_call",
    "text_completion": "llm_call",
    "execute_tool": "tool_use",
    "invoke_agent": "agent",
}


def import_otlp(path: Path) -> list[Span]:
    """Import an OTLP JSON or JSONL file into ai-team spans.

    Args:
        path: A JSON document or JSONL of span objects. Content is not required.

    Returns:
        Spans in file order. ``execute_tool`` spans that have ended also emit
        a ``tool_result``.
    """
    spans: list[Span] = []
    for index, row in enumerate(_rows(path)):
        spans.extend(_map_row(row, index))
    return spans


def kind_counts(spans: list[Span]) -> dict[str, int]:
    """Count spans by type."""
    return dict(Counter(span.type for span in spans))


def note_second_reader(trace: Trace, otel_path: Path) -> Trace:
    """Prefer harness spans and record the OTel import as a second reader.

    When the OTel file is missing, or the harness wrote no spans, the trace
    is returned unchanged. A count mismatch is kept on ``raw_result``; the
    harness span list is not replaced.
    """
    if not otel_path.is_file() or not trace.spans:
        return trace
    otel_spans = import_otlp(otel_path)
    raw = dict(trace.raw_result)
    raw["second_reader"] = {
        "name": "otel",
        "span_count": len(otel_spans),
        "preferred": "harness",
        "harness_span_count": len(trace.spans),
    }
    warnings = list(trace.warnings)
    warnings.append(
        f"second reader otel span_count={len(otel_spans)}; harness spans preferred "
        f"({len(trace.spans)})"
    )
    return trace.model_copy(update={"raw_result": raw, "warnings": warnings})


def _rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            resource = data.get("resourceSpans")
            if isinstance(resource, list):
                return _flatten_resource_spans(resource)
            return [data]
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            resource = parsed.get("resourceSpans")
            if isinstance(resource, list):
                # One OTLP request per line: the collector's file exporter and export-otel.
                rows.extend(_flatten_resource_spans(resource))
            else:
                rows.append(parsed)
    return rows


def _flatten_resource_spans(resource_spans: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for resource in resource_spans:
        if not isinstance(resource, dict):
            continue
        for scope in resource.get("scopeSpans") or []:
            if not isinstance(scope, dict):
                continue
            for span in scope.get("spans") or []:
                if isinstance(span, dict):
                    rows.append(span)
    return rows


def _attr_value(value: Any) -> Any:
    """Unwrap an OTLP ``AnyValue`` (``{"stringValue": ...}``) into a plain value."""
    if not isinstance(value, dict):
        return value
    for key in ("stringValue", "boolValue", "doubleValue"):
        if key in value:
            return value[key]
    if "intValue" in value:
        try:
            return int(value["intValue"])
        except (TypeError, ValueError):
            return value["intValue"]
    if "arrayValue" in value:
        values = (value.get("arrayValue") or {}).get("values") or []
        return [_attr_value(v) for v in values]
    return value


def _attributes(row: dict[str, Any]) -> dict[str, Any]:
    """Attributes as a flat dict, from either a flat dict or OTLP's list of key/values."""
    raw = row.get("attributes")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        out: dict[str, Any] = {}
        for item in raw:
            if isinstance(item, dict) and "key" in item:
                out[str(item["key"])] = _attr_value(item.get("value"))
        return out
    return {}


def _map_own_export(row: dict[str, Any], attributes: dict[str, Any], index: int) -> list[Span]:
    """Read back a span written by ``otel_export``: exact types, roles, phases, times."""
    span_type = str(attributes.get("ai_team.span.type"))
    if span_type == "run":
        return []  # the synthetic root; the trace itself has no such span
    merged = attributes.get("ai_team.span.merged")
    types = [str(t) for t in merged] if isinstance(merged, list) and merged else [span_type]
    started = _ts(row.get("startTimeUnixNano"), required=True) or datetime.now(UTC)
    ended = _ts(row.get("endTimeUnixNano"), required=False) or started
    role = attributes.get("ai_team.role")
    phase = attributes.get("ai_team.phase")
    out: list[Span] = []
    for n, kind in enumerate(types):
        at = started if n == 0 else ended
        single_end = ended if len(types) == 1 else at
        out.append(
            Span(
                span_id=f"otel_{index:04d}_{n}",
                type=kind,  # type: ignore[arg-type]
                t_start=at,
                t_end=single_end,
                agent_role=str(role) if role is not None else None,
                phase=str(phase) if phase is not None else None,
                payload={"name": row.get("name"), "source": "otel_export"},
            )
        )
    return out


def _map_row(row: dict[str, Any], index: int) -> list[Span]:
    attributes = _attributes(row)
    if "ai_team.span.type" in attributes:
        return _map_own_export(row, attributes, index)
    operation = attributes.get("gen_ai.operation.name") or row.get("name") or ""
    key = str(operation).strip()
    kind = SPAN_KIND_MAP.get(key, "other")
    started = _ts(row.get("startTimeUnixNano") or row.get("timestamp"), required=True)
    if started is None:
        started = datetime.now(UTC)
    ended = _ts(row.get("endTimeUnixNano") or row.get("end_time"), required=False)
    span = Span(
        span_id=f"otel_{index:04d}",
        type=kind,  # type: ignore[arg-type]
        t_start=started,
        t_end=ended,
        payload={"name": row.get("name"), "operation": key},
    )
    out = [span]
    if kind == "tool_use" and ended is not None:
        out.append(
            Span(
                span_id=f"otel_{index:04d}_result",
                type="tool_result",
                t_start=ended,
                t_end=ended,
                payload={"name": row.get("name"), "operation": key, "folded_from": "end"},
            )
        )
    return out


def _ts(value: Any, *, required: bool) -> datetime | None:
    if value is None:
        return datetime.now(UTC) if required else None
    if isinstance(value, datetime):
        return value
    try:
        nanos = int(value)
    except (TypeError, ValueError):
        return datetime.now(UTC) if required else None
    return datetime.fromtimestamp(nanos / 1_000_000_000, tz=UTC)
