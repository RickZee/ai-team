"""Assemble a Trace from live run results or an existing workspace (R1)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.provenance import collect
from evals.store import TraceStore, put_blob
from evals.trace.models import (
    SCHEMA_VERSION,
    BackendName,
    CostRecord,
    Span,
    Trace,
    TraceStatus,
)
from evals.trace.parsers import (
    parse_audit_jsonl,
    parse_costs_jsonl,
    parse_langgraph_messages,
    parse_phases_jsonl,
    parse_session_json,
    parse_smoke_report,
    scan_workspace_artifacts,
)


def make_trace_id(scenario_id: str, backend: str, when: datetime | None = None) -> str:
    """Build ``trace_id`` per R1.3."""
    ts = when or datetime.now(UTC)
    compact = ts.strftime("%Y%m%dT%H%M%SZ")
    short = uuid.uuid4().hex[:4]
    return f"{scenario_id}__{backend}__{compact}__{short}"


def _normalize_backend(backend: str) -> BackendName:
    mapping: dict[str, BackendName] = {
        "crewai": "crewai",
        "langgraph": "langgraph",
        "claude-agent-sdk": "claude-agent-sdk",
        "claude_agent_sdk": "claude-agent-sdk",
        "claude": "claude-agent-sdk",
    }
    return mapping.get(backend.strip().lower(), "crewai")


def _normalize_status(raw: str | None) -> TraceStatus:
    if not raw:
        return "failed"
    value = raw.strip().lower()
    aliases = {
        "complete": "complete",
        "completed": "complete",
        "success": "complete",
        "succeeded": "complete",
        "failed": "failed",
        "failure": "failed",
        "error": "failed",
        "awaiting_human": "awaiting_human",
        "human": "awaiting_human",
        "killed": "killed",
        "timeout": "killed",
        "budget_abort": "budget_abort",
        "skipped_budget": "budget_abort",
    }
    return aliases.get(value, "failed")  # type: ignore[return-value]


def _merge_costs(*records: CostRecord | None) -> CostRecord:
    """Prefer sdk_reported > provider_usage > token_estimate > unknown."""
    priority = {"sdk_reported": 0, "provider_usage": 1, "token_estimate": 2, "unknown": 3}
    chosen: CostRecord | None = None
    for rec in records:
        if rec is None:
            continue
        if chosen is None or priority[rec.source] < priority[chosen.source]:
            chosen = rec
        elif chosen is not None and priority[rec.source] == priority[chosen.source]:
            usd = chosen.usd if chosen.usd is not None else rec.usd
            inp = chosen.input_tokens if chosen.input_tokens is not None else rec.input_tokens
            out = chosen.output_tokens if chosen.output_tokens is not None else rec.output_tokens
            per_model = {**rec.per_model, **chosen.per_model}
            chosen = CostRecord(
                usd=usd,
                input_tokens=inp,
                output_tokens=out,
                source=chosen.source,
                per_model=per_model,
            )
    return chosen or CostRecord(usd=None, input_tokens=None, output_tokens=None, source="unknown")


def _assign_span_ids(spans: list[Span]) -> list[Span]:
    ordered = sorted(spans, key=lambda s: (s.t_start, s.type, s.span_id))
    out: list[Span] = []
    for i, span in enumerate(ordered):
        out.append(span.model_copy(update={"span_id": f"span_{i:04d}"}))
    return out


def _scenario_sha(scenario: dict[str, Any] | None, scenario_path: Path | None) -> str:
    if scenario_path is not None and scenario_path.is_file():
        return hashlib.sha256(scenario_path.read_bytes()).hexdigest()
    if scenario is not None:
        blob = json.dumps(scenario, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()
    return ""


def _infer_scenario_id(workspace: Path, explicit: str | None) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if explicit:
        return explicit, warnings
    req = workspace / "docs" / "requirements.md"
    if req.is_file():
        # Heuristic: first heading or filename stem of parent
        text = req.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if line.startswith("#"):
                slug = line.lstrip("#").strip().lower().replace(" ", "-")[:64]
                if slug:
                    return slug, warnings
    warnings.append("scenario_id unknown; falling back to 'unknown'")
    return "unknown", warnings


def _infer_backend(workspace: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    session = workspace / "logs" / "session.json"
    if session.is_file():
        try:
            data = json.loads(session.read_text(encoding="utf-8"))
            for key in ("backend", "orchestrator", "framework"):
                if key in data and data[key]:
                    return str(data[key])
        except (OSError, json.JSONDecodeError):
            pass
    # Directory name heuristics
    name = workspace.name.lower()
    for candidate in ("crewai", "langgraph", "claude-agent-sdk", "claude"):
        if candidate in name:
            return candidate
    return "crewai"


class TraceBuilder:
    """Build immutable Trace documents from run artifacts."""

    def __init__(
        self,
        *,
        scenario: dict[str, Any] | None = None,
        backend: str = "crewai",
        tier: str = "B",
        seed: int | None = None,
        store: TraceStore | None = None,
        scenario_path: Path | None = None,
    ) -> None:
        self.scenario = scenario or {}
        self.backend = backend
        self.tier = tier
        self.seed = seed
        self.store = store or TraceStore()
        self.scenario_path = scenario_path

    def from_live_run(
        self,
        result: Any,
        workspace: Path,
        wall_time_s: float,
        *,
        status: str | None = None,
    ) -> Trace:
        """Build a Trace immediately after a backend subprocess finishes."""
        raw: dict[str, Any]
        if isinstance(result, dict):
            raw = result
        elif hasattr(result, "__dict__"):
            raw = dict(getattr(result, "__dict__", {}))
        else:
            raw = {"result": result}

        inferred_status = status or raw.get("status") or raw.get("current_phase")
        if raw.get("killed"):
            inferred_status = "killed"
        return self.from_workspace(
            workspace,
            scenario_id=str(self.scenario.get("id") or self.scenario.get("scenario_id") or ""),
            backend=self.backend,
            raw_result=raw,
            status=str(inferred_status) if inferred_status else None,
            wall_time_s=wall_time_s,
        )

    def from_workspace(
        self,
        workspace: Path,
        *,
        scenario_id: str | None = None,
        backend: str | None = None,
        raw_result: dict[str, Any] | None = None,
        status: str | None = None,
        wall_time_s: float | None = None,
    ) -> Trace:
        """Retroactively build a Trace from a historical workspace directory."""
        workspace = workspace.resolve()
        warnings: list[str] = []
        raw_result = raw_result or {}

        sid, sid_warnings = _infer_scenario_id(workspace, scenario_id or None)
        if not scenario_id and self.scenario.get("id"):
            sid = str(self.scenario["id"])
        warnings.extend(sid_warnings)

        backend_name = _normalize_backend(
            backend or self.backend or _infer_backend(workspace, None)
        )

        logs = workspace / "logs"
        phase_spans, w = parse_phases_jsonl(logs / "phases.jsonl")
        warnings.extend(w)
        cost_spans, cost_from_log, w = parse_costs_jsonl(logs / "costs.jsonl")
        warnings.extend(w)
        audit_spans, audit_warnings = parse_audit_jsonl(logs / "audit.jsonl")
        warnings.extend(audit_warnings)
        session_meta, cost_from_session, w = parse_session_json(logs / "session.json")
        warnings.extend(w)

        audit_missing = (not (logs / "audit.jsonl").is_file()) or any(
            "missing" in x.lower() and "audit" in x.lower() for x in audit_warnings
        )
        if audit_missing:
            msg = f"no audit log for backend={backend_name}; tool-level checks skipped"
            if msg not in warnings:
                warnings.append(msg)

        smoke_spans, w = parse_smoke_report(workspace / "docs" / "smoke_results.json")
        warnings.extend(w)

        lg_spans: list[Span] = []
        token_total: int | None = None
        state = raw_result.get("state") if isinstance(raw_result.get("state"), dict) else None
        if state is None and isinstance(raw_result.get("messages"), list):
            state = raw_result
        if isinstance(state, dict) and state.get("messages"):
            lg_spans, token_total, w = parse_langgraph_messages(state)
            warnings.extend(w)

        def _put(data: bytes) -> str:
            return put_blob(data, root=self.store.root)

        artifacts, w = scan_workspace_artifacts(workspace, put_blob=_put)
        warnings.extend(w)

        cost_from_tokens: CostRecord | None = None
        if token_total is not None and cost_from_log is None and cost_from_session is None:
            cost_from_tokens = CostRecord(
                usd=None,
                input_tokens=token_total,
                output_tokens=None,
                source="token_estimate",
            )

        cost = _merge_costs(cost_from_session, cost_from_log, cost_from_tokens)

        all_spans = _assign_span_ids(
            phase_spans + cost_spans + audit_spans + smoke_spans + lg_spans
        )

        started_at = all_spans[0].t_start if all_spans else datetime.now(UTC)
        ended_at = None
        if all_spans:
            ends = [s.t_end or s.t_start for s in all_spans]
            ended_at = max(ends)
        if wall_time_s is not None and ended_at is None:
            ended_at = started_at

        # Prefer explicit status, then session, then heuristics
        status_raw = (
            status
            or session_meta.get("status")
            or session_meta.get("final_status")
            or raw_result.get("status")
        )
        if not status_raw and (logs / "phases.jsonl").is_file():
            status_raw = "complete" if phase_spans else "failed"
        norm_status = _normalize_status(str(status_raw) if status_raw else None)

        scenario_sha = _scenario_sha(self.scenario or None, self.scenario_path)
        provenance = collect(
            seed=self.seed,
            tier=self.tier,
            scenario_content_sha256=scenario_sha,
            model_ids=dict(session_meta.get("model_ids") or {}),
        )

        return Trace(
            schema_version=SCHEMA_VERSION,
            trace_id=make_trace_id(sid, backend_name, started_at),
            scenario_id=sid,
            backend=backend_name,
            status=norm_status,
            started_at=started_at,
            ended_at=ended_at,
            spans=all_spans,
            artifacts=artifacts,
            cost=cost,
            provenance=provenance,
            warnings=warnings,
            raw_result=raw_result,
            workspace_dir=str(workspace),
        )
