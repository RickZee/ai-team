"""Log and workspace parsers that emit provisional Spans / Artifacts / CostRecords.

Each public parser returns results plus a ``warnings`` list and **never raises** on
missing files, truncated lines, or malformed JSON (R1.6). Provisional ``span_id``
values (e.g. ``phases_0000``) are reassigned later by :class:`TraceBuilder`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.trace.models import Artifact, ArtifactKind, CostRecord, CostSource, Span, SpanType

_TEXT_TRUNCATE_BYTES = 256 * 1024
_TRUNCATION_MARKER = b"\n[TRUNCATED at 256KB]"
_SKIP_DIR_NAMES = frozenset({".git", "__pycache__", "node_modules", ".venv"})

_PHASE_START_STATUSES = frozenset(
    {"started", "start", "begin", "in_progress", "running", "phase_start"}
)
_PHASE_END_STATUSES = frozenset(
    {"completed", "complete", "ended", "end", "finished", "done", "success", "phase_end"}
)
_RETRY_STATUSES = frozenset({"retry", "retried", "retrying"})

_CONFIG_NAMES = frozenset({"dockerfile", "docker-compose.yml", "docker-compose.yaml"})
_CONFIG_SUFFIXES = frozenset({".yml", ".yaml", ".toml", ".tf"})


def _parse_ts(value: Any, warnings: list[str]) -> datetime:
    """Parse *value* to a timezone-aware UTC datetime.

    Unparseable values fall back to ``datetime.now(UTC)`` and append a warning.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if value is None:
        warnings.append("unparseable timestamp: None; using now()")
        return datetime.now(UTC)
    text = str(value).strip()
    if not text:
        warnings.append("unparseable timestamp: empty; using now()")
        return datetime.now(UTC)
    try:
        # Support trailing Z
        normalized = text.replace("Z", "+00:00") if text.endswith("Z") else text
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (TypeError, ValueError):
        warnings.append(f"unparseable timestamp: {value!r}; using now()")
        return datetime.now(UTC)


def _read_jsonl_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Load JSONL objects from *path*; never raise on malformed content."""
    warnings: list[str] = []
    if not path.is_file():
        return [], [f"missing: {path}"]

    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [], [f"unreadable: {path}: {e}"]

    rows: list[dict[str, Any]] = []
    lines = raw.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            is_last = idx == len(lines) - 1 or all(not ln.strip() for ln in lines[idx + 1 :])
            if is_last:
                warnings.append(f"truncated final line in {path.name} (line {idx + 1})")
            else:
                warnings.append(f"invalid JSON in {path.name} (line {idx + 1})")
            continue
        if not isinstance(obj, dict):
            warnings.append(f"non-object JSON in {path.name} (line {idx + 1})")
            continue
        rows.append(obj)
    return rows, warnings


def _provisional_id(prefix: str, index: int) -> str:
    return f"{prefix}_{index:04d}"


def _map_phase_status(status: str) -> SpanType | None:
    """Map a phases.jsonl status string to a span type."""
    key = status.strip().lower()
    if key in _PHASE_START_STATUSES:
        return "phase_start"
    if key in _PHASE_END_STATUSES:
        return "phase_end"
    if key in _RETRY_STATUSES:
        return "retry"
    if "retry" in key:
        return "retry"
    if key.endswith("_start") or key.startswith("start"):
        return "phase_start"
    if key.endswith("_end") or key.startswith("end"):
        return "phase_end"
    return None


def parse_phases_jsonl(path: Path) -> tuple[list[Span], list[str]]:
    """Parse ``logs/phases.jsonl`` into provisional phase / retry spans.

    Expected line shape: ``{phase, status, timestamp}`` (agent-written). Status
    values map to ``phase_start``, ``phase_end``, or ``retry``.

    Args:
        path: Path to the JSONL file.

    Returns:
        Spans with ids ``phases_NNNN``, plus warnings for gaps.
    """
    rows, warnings = _read_jsonl_rows(path)
    spans: list[Span] = []
    for row in rows:
        status = str(row.get("status") or "")
        span_type = _map_phase_status(status)
        if span_type is None:
            warnings.append(f"unknown phase status: {status!r}; skipping")
            continue
        phase = row.get("phase") or row.get("name")
        phase_str = str(phase) if phase is not None else None
        ts = _parse_ts(row.get("timestamp") or row.get("ts") or row.get("t"), warnings)
        agent = row.get("agent_role") or row.get("agent") or row.get("role")
        spans.append(
            Span(
                span_id=_provisional_id("phases", len(spans)),
                type=span_type,
                t_start=ts,
                t_end=ts,
                phase=phase_str,
                agent_role=str(agent) if agent is not None else None,
                payload={k: v for k, v in row.items() if k not in ("timestamp", "ts", "t")},
            )
        )
    return spans, warnings


def _usage_tokens(usage: Any) -> tuple[int | None, int | None]:
    """Extract input/output token counts from a usage mapping."""
    if not isinstance(usage, dict):
        return None, None
    inp = usage.get("input_tokens") or usage.get("prompt_tokens") or usage.get("input")
    out = usage.get("output_tokens") or usage.get("completion_tokens") or usage.get("output")
    try:
        inp_i = int(inp) if inp is not None else None
    except (TypeError, ValueError):
        inp_i = None
    try:
        out_i = int(out) if out is not None else None
    except (TypeError, ValueError):
        out_i = None
    return inp_i, out_i


def _coerce_cost(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_costs_jsonl(path: Path) -> tuple[list[Span], CostRecord | None, list[str]]:
    """Parse ``logs/costs.jsonl`` into spend / llm spans and an aggregate cost.

    Supports Claude SDK rows ``{phase, cost_usd, usage, timestamp}`` and results
    writer rows ``{timestamp, kind: "run_total", ...}``.

    Args:
        path: Path to the JSONL file.

    Returns:
        Spans (``spend_event``, ``llm_call``), optional aggregated
        :class:`CostRecord`, and warnings.
    """
    rows, warnings = _read_jsonl_rows(path)
    spans: list[Span] = []
    total_usd = 0.0
    saw_usd = False
    total_in = 0
    total_out = 0
    saw_in = False
    saw_out = False
    saw_run_total = False
    saw_provider = False

    for row in rows:
        ts = _parse_ts(row.get("timestamp") or row.get("ts"), warnings)
        phase = row.get("phase")
        phase_str = str(phase) if phase is not None else None
        kind = str(row.get("kind") or "")
        usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
        cost = _coerce_cost(row.get("cost_usd") or row.get("cost") or row.get("total_cost_usd"))
        if cost is None and isinstance(usage, dict):
            cost = _coerce_cost(usage.get("cost") or usage.get("response_cost"))

        if kind == "run_total":
            saw_run_total = True
        if cost is not None:
            saw_usd = True
            total_usd += cost
            if kind != "run_total":
                saw_provider = True

        inp, out = _usage_tokens(usage)
        if inp is not None:
            saw_in = True
            total_in += inp
        if out is not None:
            saw_out = True
            total_out += out

        # Always emit a spend_event when there is a cost or run_total row.
        if cost is not None or kind == "run_total":
            spans.append(
                Span(
                    span_id=_provisional_id("costs", len(spans)),
                    type="spend_event",
                    t_start=ts,
                    t_end=ts,
                    phase=phase_str,
                    payload=dict(row),
                )
            )

        # Emit llm_call when usage looks like a model call.
        has_usage = bool(usage) or inp is not None or out is not None
        if has_usage and kind != "run_total":
            spans.append(
                Span(
                    span_id=_provisional_id("costs", len(spans)),
                    type="llm_call",
                    t_start=ts,
                    t_end=ts,
                    phase=phase_str,
                    payload={
                        "usage": usage,
                        "cost_usd": cost,
                        "source": "costs.jsonl",
                    },
                )
            )

    cost_record: CostRecord | None = None
    if saw_usd or saw_in or saw_out:
        # Phase rows with cost/usage → provider_usage; run_total-only → sdk_reported.
        source: CostSource
        if saw_provider or saw_in or saw_out:
            source = "provider_usage"
        elif saw_run_total:
            source = "sdk_reported"
        else:
            source = "sdk_reported" if saw_usd else "unknown"
        cost_record = CostRecord(
            usd=total_usd if saw_usd else None,
            input_tokens=total_in if saw_in else None,
            output_tokens=total_out if saw_out else None,
            source=source,
        )
    return spans, cost_record, warnings


def _map_audit_event(row: dict[str, Any]) -> SpanType | None:
    """Map a flexible audit / hook row to a span type."""
    raw = row.get("type") or row.get("event") or row.get("hook_event_name") or row.get("kind") or ""
    key = str(raw).strip().lower().replace("-", "").replace("_", "")

    if key in {"pretooluse", "tooluse", "tool_call", "toolcall"}:
        return "tool_use"
    if key in {"posttooluse", "toolresult", "tool_result"}:
        return "tool_result"
    if key in {"subagentstart", "subagent_start"}:
        return "subagent_start"
    if key in {"subagentstop", "subagent_end", "subagent_stop"}:
        return "subagent_stop"
    if "guardrail" in key or "security" in key or "quality" in key:
        return "guardrail_check"
    if row.get("category") in ("security", "quality", "guardrail"):
        return "guardrail_check"
    if row.get("result") is not None and (row.get("tool") or row.get("tool_name")):
        # Result-bearing tool row without a clear event → tool_result
        return "tool_result"
    if row.get("tool") or row.get("tool_name"):
        return "tool_use"
    return None


def parse_audit_jsonl(path: Path) -> tuple[list[Span], list[str]]:
    """Parse Claude SDK ``logs/audit.jsonl`` hook events into spans.

    Accepts flexible shapes with ``type`` / ``event`` / ``tool_name`` / ``tool`` /
    ``phase`` / ``timestamp`` / ``result``. Maps to ``tool_use``, ``tool_result``,
    ``guardrail_check``, ``subagent_start``, and ``subagent_stop``.

    Args:
        path: Path to the JSONL file.

    Returns:
        Spans with ids ``audit_NNNN``, plus warnings.
    """
    rows, warnings = _read_jsonl_rows(path)
    spans: list[Span] = []
    for row in rows:
        span_type = _map_audit_event(row)
        if span_type is None:
            warnings.append(
                f"unrecognized audit event: {row.get('event') or row.get('type')!r}; skipping"
            )
            continue
        ts = _parse_ts(row.get("timestamp") or row.get("ts"), warnings)
        phase = row.get("phase")
        agent = row.get("agent_role") or row.get("agent_type") or row.get("agent")
        spans.append(
            Span(
                span_id=_provisional_id("audit", len(spans)),
                type=span_type,
                t_start=ts,
                t_end=ts,
                phase=str(phase) if phase is not None else None,
                agent_role=str(agent) if agent is not None else None,
                payload=dict(row),
            )
        )
    return spans, warnings


def parse_session_json(path: Path) -> tuple[dict[str, Any], CostRecord | None, list[str]]:
    """Parse ``logs/session.json`` into metadata and optional SDK cost.

    Args:
        path: Path to the JSON session file.

    Returns:
        Session metadata dict, optional :class:`CostRecord` with
        ``source='sdk_reported'`` when ``total_cost_usd`` is present, and warnings.
    """
    warnings: list[str] = []
    if not path.is_file():
        return {}, None, [f"missing: {path}"]

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {}, None, [f"unreadable: {path}: {e}"]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}, None, [f"invalid JSON in {path.name}"]

    if not isinstance(data, dict):
        return {}, None, [f"non-object JSON in {path.name}"]

    cost_record: CostRecord | None = None
    cost = _coerce_cost(data.get("total_cost_usd"))
    if cost is not None:
        cost_record = CostRecord(
            usd=cost,
            input_tokens=None,
            output_tokens=None,
            source="sdk_reported",
        )
    return dict(data), cost_record, warnings


def _extract_total_tokens(state: dict[str, Any]) -> int | None:
    """Sum token counts from LangGraph message metadata.

    Ported from :func:`evals.metrics._extract_total_tokens` — keep behaviour
    identical so cost normalization stays consistent across call sites.
    """
    total = 0
    found = False
    for msg in state.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        usage = (msg.get("response_metadata") or {}).get("token_usage") or {}
        if not usage and isinstance(msg, dict):
            usage = msg.get("usage_metadata") or {}
        t = usage.get("total_tokens") or 0
        if t:
            total += t
            found = True
    return total if found else None


def parse_langgraph_messages(
    state: dict[str, Any],
) -> tuple[list[Span], int | None, list[str]]:
    """Emit ``llm_call`` spans from a LangGraph state dict and sum tokens.

    Token summing is ported from :func:`evals.metrics._extract_total_tokens`.

    Args:
        state: LangGraph (or compatible) state containing a ``messages`` list.

    Returns:
        Spans, total token count (or None), and warnings.
    """
    warnings: list[str] = []
    if not isinstance(state, dict):
        return [], None, ["langgraph state is not a dict"]

    messages = state.get("messages")
    if messages is None:
        return [], None, ["langgraph state missing messages"]
    if not isinstance(messages, list):
        return [], None, ["langgraph messages is not a list"]

    spans: list[Span] = []
    now = datetime.now(UTC)
    for msg in messages:
        if not isinstance(msg, dict):
            warnings.append("skipping non-dict langgraph message")
            continue
        usage = (msg.get("response_metadata") or {}).get("token_usage") or {}
        if not usage:
            usage = msg.get("usage_metadata") or {}
        if not isinstance(usage, dict):
            usage = {}
        # Prefer messages that look like model turns (have usage or role=ai/assistant)
        role = str(msg.get("type") or msg.get("role") or "").lower()
        has_usage = bool(usage)
        if not has_usage and role not in {"ai", "assistant", "aimessage"}:
            continue
        ts_raw = msg.get("timestamp") or (msg.get("response_metadata") or {}).get("created_at")
        ts = _parse_ts(ts_raw, warnings) if ts_raw is not None else now
        spans.append(
            Span(
                span_id=_provisional_id("lgmsg", len(spans)),
                type="llm_call",
                t_start=ts,
                t_end=ts,
                payload={
                    "role": role or None,
                    "usage": usage,
                    "content_preview": str(msg.get("content") or "")[:200],
                },
            )
        )

    total_tokens = _extract_total_tokens(state)
    return spans, total_tokens, warnings


def _classify_artifact(rel_posix: str) -> ArtifactKind:
    """Classify a workspace-relative path into an artifact kind."""
    name = Path(rel_posix).name
    lower_name = name.lower()
    if lower_name in _CONFIG_NAMES or Path(rel_posix).suffix.lower() in _CONFIG_SUFFIXES:
        return "config"
    parts = rel_posix.split("/")
    top = parts[0] if parts else ""
    if top == "src":
        return "source"
    if top == "tests":
        return "test"
    if top == "docs":
        return "doc"
    if top == "logs":
        return "log"
    return "other"


def _hash_file_content(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _prepare_text_for_hash(raw: bytes) -> bytes:
    """Truncate UTF-8 text above 256KB with the standard marker before hashing."""
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    if len(raw) <= _TEXT_TRUNCATE_BYTES:
        return raw
    return raw[:_TEXT_TRUNCATE_BYTES] + _TRUNCATION_MARKER


def scan_workspace_artifacts(
    workspace: Path,
    *,
    put_blob: Callable[[bytes], str] | None = None,
) -> tuple[list[Artifact], list[str]]:
    """Walk *workspace* and build an artifact inventory with content hashes.

    Skips ``.git``, ``__pycache__``, ``node_modules``, and ``.venv``. When
    *put_blob* is provided, content is stored via that callback and its returned
    sha is used; otherwise content is hashed in-place (text over 256KB is
    truncated with ``\\n[TRUNCATED at 256KB]`` before hashing).

    Args:
        workspace: Root directory to scan.
        put_blob: Optional content-addressed store callback ``bytes -> sha256``.

    Returns:
        Artifact list and warnings.
    """
    warnings: list[str] = []
    if not workspace.is_dir():
        return [], [f"missing: {workspace}"]

    artifacts: list[Artifact] = []
    try:
        for path in sorted(workspace.rglob("*")):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(workspace)
            except ValueError:
                warnings.append(f"path outside workspace: {path}")
                continue
            if any(part in _SKIP_DIR_NAMES for part in rel.parts):
                continue
            rel_posix = rel.as_posix()
            try:
                raw = path.read_bytes()
            except OSError as e:
                warnings.append(f"unreadable artifact {rel_posix}: {e}")
                continue

            prepared = _prepare_text_for_hash(raw)
            if put_blob is not None:
                try:
                    sha = put_blob(prepared)
                except (OSError, TypeError, ValueError, RuntimeError) as e:
                    warnings.append(f"put_blob failed for {rel_posix}: {e}")
                    sha = _hash_file_content(prepared)
            else:
                sha = _hash_file_content(prepared)

            artifacts.append(
                Artifact(
                    path=rel_posix,
                    size_bytes=len(raw),
                    sha256=sha,
                    kind=_classify_artifact(rel_posix),
                )
            )
    except OSError as e:
        warnings.append(f"workspace walk failed: {e}")

    return artifacts, warnings


def parse_smoke_report(path: Path) -> tuple[list[Span], list[str]]:
    """Parse ``docs/smoke_results.json`` into ``smoke_probe`` span(s).

    Expected shape from :mod:`ai_team.tools.smoke_tools`: ``ran``, ``success``,
    ``entrypoint``, ``probes``, ``message``.

    Args:
        path: Path to the smoke results JSON file.

    Returns:
        One overview span plus per-probe spans when ``probes`` is present,
        and warnings.
    """
    warnings: list[str] = []
    if not path.is_file():
        return [], [f"missing: {path}"]

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [], [f"unreadable: {path}: {e}"]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [], [f"invalid JSON in {path.name}"]

    if not isinstance(data, dict):
        return [], [f"non-object JSON in {path.name}"]

    ts = _parse_ts(data.get("timestamp"), warnings) if data.get("timestamp") else datetime.now(UTC)
    spans: list[Span] = [
        Span(
            span_id=_provisional_id("smoke", 0),
            type="smoke_probe",
            t_start=ts,
            t_end=ts,
            phase="testing",
            payload={
                "ran": data.get("ran"),
                "success": data.get("success"),
                "entrypoint": data.get("entrypoint"),
                "message": data.get("message"),
                "base_url": data.get("base_url"),
                "probe_count": len(data.get("probes") or [])
                if isinstance(data.get("probes"), list)
                else 0,
            },
        )
    ]

    probes = data.get("probes")
    if isinstance(probes, list):
        for probe in probes:
            if not isinstance(probe, dict):
                warnings.append("skipping non-dict smoke probe entry")
                continue
            spans.append(
                Span(
                    span_id=_provisional_id("smoke", len(spans)),
                    type="smoke_probe",
                    t_start=ts,
                    t_end=ts,
                    phase="testing",
                    payload=dict(probe),
                )
            )
    return spans, warnings


def parse_qa_verdicts_jsonl(path: Path) -> tuple[list[Span], list[str]]:
    """Parse ``docs/qa_verdicts.jsonl`` into ``qa_verdict`` spans.

    A missing file is not a warning — QA verdicts are optional until a QA pass
    runs (harness-alignment R16.2).
    """
    if not path.is_file():
        return [], []
    rows, warnings = _read_jsonl_rows(path)
    spans: list[Span] = []
    for row in rows:
        ts = _parse_ts(row.get("emitted_at") or row.get("timestamp"), warnings)
        identity = row.get("identity")
        agent = None
        if isinstance(identity, dict):
            raw_agent = identity.get("agent_role")
            agent = str(raw_agent) if raw_agent is not None else None
        spans.append(
            Span(
                span_id=_provisional_id("qa", len(spans)),
                type="qa_verdict",
                t_start=ts,
                t_end=ts,
                phase="testing",
                agent_role=agent,
                payload=dict(row),
            )
        )
    return spans, warnings


def parse_ui_smoke_report(path: Path) -> tuple[list[Span], list[str]]:
    """Parse ``docs/ui_smoke_results.json`` into ``smoke_probe`` spans with ``kind=ui``.

    A missing file is not a warning — UI smoke is optional unless the scenario
    declares a ``ui`` block.
    """
    if not path.is_file():
        return [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], [f"unreadable ui_smoke_results: {exc}"]
    if not isinstance(data, dict):
        return [], [f"non-object JSON in {path.name}"]
    raw_ts = data.get("started_at") or data.get("timestamp")
    ts = _parse_ts(raw_ts, []) if raw_ts else datetime.now(UTC)
    payload = dict(data)
    payload.setdefault("kind", "ui")
    return (
        [
            Span(
                span_id=_provisional_id("uismoke", 0),
                type="smoke_probe",
                t_start=ts,
                t_end=ts,
                phase="testing",
                payload=payload,
            )
        ],
        [],
    )


def parse_sessions_jsonl(path: Path) -> tuple[list[Span], list[str]]:
    """Parse ``logs/sessions.jsonl`` into session_start / session_end / regression_check.

    Absence is silent — the session loop is off by default.
    """
    if not path.is_file():
        return [], []
    rows, warnings = _read_jsonl_rows(path)
    spans: list[Span] = []
    for row in rows:
        started = _parse_ts(row.get("started_at"), warnings)
        ended = _parse_ts(row.get("ended_at"), warnings) if row.get("ended_at") else started
        spans.append(
            Span(
                span_id=_provisional_id("sess_start", len(spans)),
                type="session_start",
                t_start=started,
                t_end=started,
                payload={"session_id": row.get("session_id"), "index": row.get("index")},
            )
        )
        spans.append(
            Span(
                span_id=_provisional_id("sess_end", len(spans)),
                type="session_end",
                t_start=ended,
                t_end=ended,
                payload={
                    "session_id": row.get("session_id"),
                    "status": row.get("status"),
                    "termination_reason": row.get("termination_reason"),
                    "context_pressure": row.get("context_pressure_at_end"),
                },
            )
        )
        if row.get("items_demoted"):
            spans.append(
                Span(
                    span_id=_provisional_id("regress", len(spans)),
                    type="regression_check",
                    t_start=ended,
                    t_end=ended,
                    payload={
                        "demoted": row.get("items_demoted"),
                        "passed": row.get("items_passed"),
                    },
                )
            )
    return spans, warnings
