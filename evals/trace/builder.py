"""Assemble a Trace from live run results or an existing workspace (R1)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
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
    parse_qa_disagreements_jsonl,
    parse_qa_verdicts_jsonl,
    parse_session_json,
    parse_sessions_jsonl,
    parse_smoke_report,
    parse_ui_smoke_report,
    scan_workspace_artifacts,
)


def make_trace_id(scenario_id: str, backend: str, when: datetime | None = None) -> str:
    """Build ``trace_id`` per R1.3."""
    ts = when or datetime.now(UTC)
    compact = ts.strftime("%Y%m%dT%H%M%SZ")
    short = uuid.uuid4().hex[:4]
    return f"{scenario_id}__{backend}__{compact}__{short}"


@dataclass(frozen=True)
class _Telemetry:
    """Everything the log files of one run contribute to its trace."""

    phase_spans: list[Span]
    cost_spans: list[Span]
    audit_spans: list[Span]
    smoke_spans: list[Span]
    ui_spans: list[Span]
    qa_spans: list[Span]
    disagreement_spans: list[Span]
    session_spans: list[Span]
    session_meta: dict[str, Any]
    cost_from_log: CostRecord | None
    cost_from_session: CostRecord | None
    audit_missing: bool
    warnings: list[str]


def _read_telemetry(run_dir: Path, run_record: dict[str, Any]) -> _Telemetry:
    """Parse every log a run wrote, across both trees it writes to.

    Extracted from ``from_workspace`` because adding the second tree pushed it past the repo's
    150-line function ratchet, which says to extract rather than raise the floor.
    """
    warnings: list[str] = []
    alt_root = _agent_workspace_root(run_dir, run_record)
    read_from_workspace: list[str] = []

    def _src(rel: str) -> Path:
        """Prefer the run directory; fall back to the agent workspace."""
        primary = run_dir / rel
        if primary.is_file() or alt_root is None:
            return primary
        alt = alt_root / rel
        if alt.is_file():
            read_from_workspace.append(rel)
            return alt
        return primary

    phase_spans, w = parse_phases_jsonl(_src("logs/phases.jsonl"))
    warnings.extend(w)
    cost_spans, cost_from_log, w = parse_costs_jsonl(_src("logs/costs.jsonl"))
    warnings.extend(w)
    audit_path = _src("logs/audit.jsonl")
    audit_spans, audit_warnings = parse_audit_jsonl(audit_path)
    warnings.extend(audit_warnings)
    session_meta, cost_from_session, w = parse_session_json(_src("logs/session.json"))
    warnings.extend(w)
    smoke_spans, w = parse_smoke_report(_src("docs/smoke_results.json"))
    warnings.extend(w)
    ui_spans, w = parse_ui_smoke_report(_src("docs/ui_smoke_results.json"))
    warnings.extend(w)
    qa_spans, w = parse_qa_verdicts_jsonl(_src("docs/qa_verdicts.jsonl"))
    warnings.extend(w)
    disagreement_spans, w = parse_qa_disagreements_jsonl(_src("logs/qa_disagreements.jsonl"))
    warnings.extend(w)
    session_spans, w = parse_sessions_jsonl(_src("logs/sessions.jsonl"))
    warnings.extend(w)
    if read_from_workspace:
        warnings.append(
            "telemetry read from the agent workspace rather than the run directory: "
            + ", ".join(sorted(set(read_from_workspace)))
        )

    audit_missing = (not audit_path.is_file()) or any(
        "missing" in x.lower() and "audit" in x.lower() for x in audit_warnings
    )
    return _Telemetry(
        phase_spans=phase_spans,
        cost_spans=cost_spans,
        audit_spans=audit_spans,
        smoke_spans=smoke_spans,
        ui_spans=ui_spans,
        qa_spans=qa_spans,
        disagreement_spans=disagreement_spans,
        session_spans=session_spans,
        session_meta=session_meta,
        cost_from_log=cost_from_log,
        cost_from_session=cost_from_session,
        audit_missing=audit_missing,
        warnings=warnings,
    )


def _otel_sidecar(workspace: Path, run_record: dict[str, Any]) -> Path:
    """OTel JSONL next to the run, or in the agent workspace when that is where it landed."""
    primary = workspace / "logs" / "otel.jsonl"
    if primary.is_file():
        return primary
    alt = _agent_workspace_root(workspace, run_record)
    if alt is not None:
        candidate = alt / "logs" / "otel.jsonl"
        if candidate.is_file():
            return candidate
    return primary


def _agent_workspace_root(run_dir: Path, run_record: dict[str, Any]) -> Path | None:
    """Locate the agent's workspace for a run, which is a different tree from its run record.

    A run writes two trees. ``output/runs/<id>/`` holds the record, the artifacts and
    ``logs/costs.jsonl``. ``workspace/<id>/`` — where the agents actually worked — holds
    ``logs/audit.jsonl`` (every tool call), ``docs/qa_verdicts.jsonl``, the journal and the
    acceptance log. This builder read only the first tree, so on 2026-09-18 a corpus of 385
    traces contained 0 phase spans and 0 tool spans: every span in it was a cost row, because
    ``costs.jsonl`` is the one telemetry file written next to the record. Thirty fresh runs
    added thirty more single-span traces, and ``CHK-trace-has-spans`` passed all of them.

    It is week 3's lesson one level down — the writer and the reader disagree about where a run
    lives — and the path was in ``run.json`` the whole time.

    ``workspace_dir`` is absolute and recorded on the machine that ran it, so it does not
    resolve on a different host or through a mount. Fall back to the layout convention,
    ``<repo>/workspace/<project_id>`` beside ``<repo>/output/runs/<project_id>``.
    """
    recorded = run_record.get("workspace_dir")
    if isinstance(recorded, str) and recorded:
        candidate = Path(recorded)
        if candidate.is_dir() and candidate.resolve() != run_dir:
            return candidate.resolve()
    try:
        sibling = run_dir.parents[2] / "workspace" / run_dir.name
    except IndexError:
        return None
    return sibling.resolve() if sibling.is_dir() else None


def _normalize_backend(backend: str | None) -> BackendName:
    """Map a backend label to :data:`BackendName`; anything unrecognised is ``unknown``."""
    mapping: dict[str, BackendName] = {
        "crewai": "crewai",
        "langgraph": "langgraph",
        "claude-agent-sdk": "claude-agent-sdk",
        "claude_agent_sdk": "claude-agent-sdk",
        "claude": "claude-agent-sdk",
        "strands": "strands",
        "agent-framework": "agent-framework",
        "agent_framework": "agent-framework",
    }
    if not backend:
        return "unknown"
    return mapping.get(backend.strip().lower(), "unknown")


def _read_json(path: Path) -> dict[str, Any]:
    """Return a JSON object from *path*, or ``{}`` when absent or unreadable."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _as_dict(value: Any) -> dict[str, Any]:
    """*value* when it is a dict, else an empty dict."""
    return value if isinstance(value, dict) else {}


def _parse_ts(value: Any) -> datetime | None:
    """Parse an ISO timestamp from a run record; ``None`` when absent or malformed."""
    if not isinstance(value, str) or not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _run_record_status(run: dict[str, Any], state: dict[str, Any]) -> str | None:
    """Final status as the harness recorded it in ``run.json`` / ``state.json``.

    ``run.json`` nests it under ``extra`` (see ``ResultsBundle.finalize``); readers that
    only look at the top level see nothing — the 2026-09-14 finding.
    """
    extra = _as_dict(run.get("extra"))
    for value in (run.get("final_status"), extra.get("final_status")):
        if isinstance(value, str) and value:
            return value
    inner = _as_dict(state.get("state")) or state
    monitor = _as_dict(state.get("monitor_snapshot"))
    for value in (inner.get("current_phase"), monitor.get("phase")):
        if value in ("complete", "completed"):
            return "complete"
    return None


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


def _infer_backend(workspace: Path, explicit: str | None) -> str | None:
    """Backend from what the run recorded; ``None`` when nothing says.

    Order: explicit → ``run.json`` (top level, then ``extra``) → ``logs/session.json``
    → directory name. No default: a guess here labels every unlabelled run as one
    backend, which is how a 334-run corpus once read ``crewai ×334``.
    """
    if explicit:
        return explicit
    run = _read_json(workspace / "run.json")
    extra = _as_dict(run.get("extra"))
    for value in (run.get("backend"), extra.get("backend")):
        if isinstance(value, str) and value:
            return value
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
    return None


def _resolve_clock(
    spans: list[Span],
    run_record: dict[str, Any],
    wall_time_s: float | None,
    warnings: list[str],
) -> tuple[datetime, datetime | None]:
    """Trace start/end: spans first, then the run record's own clock, never build time."""
    if spans:
        return spans[0].t_start, max(s.t_end or s.t_start for s in spans)
    rec_start = _parse_ts(run_record.get("started_at"))
    rec_end = _parse_ts(run_record.get("completed_at"))
    if rec_start is None and rec_end is None:
        warnings.append("no spans and no run-record timestamps; started_at is build time")
    started_at = rec_start or rec_end or datetime.now(UTC)
    ended_at = rec_end
    if wall_time_s is not None and ended_at is None:
        ended_at = started_at
    return started_at, ended_at


def _resolve_status(
    explicit: str | None,
    session_meta: dict[str, Any],
    raw_result: dict[str, Any],
    run_record: dict[str, Any],
    state_record: dict[str, Any],
    *,
    phases_file: bool,
    has_phase_spans: bool,
    warnings: list[str],
) -> str | None:
    """Prefer explicit status, then session, then the run record, then heuristics."""
    status_raw = (
        explicit
        or session_meta.get("status")
        or session_meta.get("final_status")
        or raw_result.get("status")
        or _run_record_status(run_record, state_record)
    )
    if not status_raw and phases_file:
        status_raw = "complete" if has_phase_spans else "failed"
    if not status_raw:
        warnings.append("no final status recorded; status defaulted to 'failed'")
    return str(status_raw) if status_raw else None


class TraceBuilder:
    """Build immutable Trace documents from run artifacts."""

    def __init__(
        self,
        *,
        scenario: dict[str, Any] | None = None,
        backend: str | None = "crewai",
        tier: str = "B",
        seed: int | None = None,
        store: TraceStore | None = None,
        scenario_path: Path | None = None,
    ) -> None:
        """Create a builder.

        Args:
            backend: Backend to stamp on every trace. Pass ``None`` to read it from each
                run's own record instead (what ``trace backfill`` does); runs that never
                recorded one become ``unknown``.
        """
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
            backend=self.backend or None,
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

        run_record = _read_json(workspace / "run.json")
        state_record = _read_json(workspace / "state.json")

        backend_name = _normalize_backend(
            backend or self.backend or _infer_backend(workspace, None)
        )
        if backend_name == "unknown":
            warnings.append("backend not recorded in run.json or session.json; set to 'unknown'")

        logs = workspace / "logs"
        tel = _read_telemetry(workspace, run_record)
        warnings.extend(tel.warnings)
        phase_spans = tel.phase_spans
        cost_spans, cost_from_log = tel.cost_spans, tel.cost_from_log
        audit_spans = tel.audit_spans
        session_meta, cost_from_session = tel.session_meta, tel.cost_from_session
        smoke_spans, ui_spans = tel.smoke_spans, tel.ui_spans
        qa_spans, session_spans = tel.qa_spans, tel.session_spans
        disagreement_spans = tel.disagreement_spans
        if tel.audit_missing:
            msg = f"no audit log for backend={backend_name}; tool-level checks skipped"
            if msg not in warnings:
                warnings.append(msg)

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
            phase_spans
            + cost_spans
            + audit_spans
            + smoke_spans
            + ui_spans
            + qa_spans
            + disagreement_spans
            + session_spans
            + lg_spans
        )

        started_at, ended_at = _resolve_clock(all_spans, run_record, wall_time_s, warnings)
        status_raw = _resolve_status(
            status,
            session_meta,
            raw_result,
            run_record,
            state_record,
            phases_file=(logs / "phases.jsonl").is_file(),
            has_phase_spans=bool(phase_spans),
            warnings=warnings,
        )
        norm_status = _normalize_status(str(status_raw) if status_raw else None)

        scenario_sha = _scenario_sha(self.scenario or None, self.scenario_path)
        provenance = collect(
            seed=self.seed,
            tier=self.tier,
            scenario_content_sha256=scenario_sha,
            model_ids=dict(session_meta.get("model_ids") or {}),
        )

        arm_id = None
        arm_file = workspace / ".arm_id"
        if arm_file.is_file():
            try:
                arm_id = arm_file.read_text(encoding="utf-8").strip() or None
            except OSError:
                arm_id = None

        from evals.trace.otel_import import note_second_reader

        trace = Trace(
            schema_version=SCHEMA_VERSION,
            trace_id=make_trace_id(sid, backend_name, started_at),
            scenario_id=sid,
            backend=backend_name,
            arm_id=arm_id,
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
        return note_second_reader(trace, _otel_sidecar(workspace, run_record))
