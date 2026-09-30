"""Map OpenTelemetry GenAI spans onto ai-team span kinds.

The mapping is one table. Unknown names become ``other`` and are counted.
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


def _map_row(row: dict[str, Any], index: int) -> list[Span]:
    raw_attributes = row.get("attributes")
    attributes = raw_attributes if isinstance(raw_attributes, dict) else {}
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
