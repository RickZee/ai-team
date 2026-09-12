"""ToolBus: the only execution path for registered tools.

Pipeline: lookup → schema validate → permission → kind branch → cap summary →
audit spans. Process-local via :func:`get_bus` / :func:`reset_bus` (ContextVar,
not a cross-run singleton — see FM-007).
"""

from __future__ import annotations

import contextvars
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from ai_team.tools.kinds import (
    LOCKFILE_PATHS,
    SUMMARY_MAX_CHARS,
    ObservationCode,
    RiskClass,
    ToolKind,
    ToolObservation,
    ToolRequest,
)
from pydantic import BaseModel, ConfigDict, ValidationError

logger = structlog.get_logger(__name__)

Handler = Callable[[dict[str, Any], ToolRequest], ToolObservation]


class EmptyArgs(BaseModel):
    """Default schema when a tool declares no arguments."""


class ToolSpec(BaseModel):
    """Registered tool metadata. Handler is excluded from serialization."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    kind: ToolKind
    risk_class: RiskClass
    args_schema: type[BaseModel] = EmptyArgs
    handler: Handler
    allow_roles: list[str] | None = None


class ToolBus:
    """Dispatcher: ``{tool, args}`` in, :class:`ToolObservation` out."""

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._spans: list[dict[str, Any]] = []
        self.allow_irreversible: bool = False

    def register(self, spec: ToolSpec) -> None:
        """Register or replace a tool spec."""
        self._specs[spec.name] = spec
        logger.debug("toolbus_registered", tool=spec.name, kind=spec.kind)

    def registered_names(self) -> list[str]:
        """Sorted registered tool names."""
        return sorted(self._specs)

    def get_spec(self, name: str) -> ToolSpec | None:
        """Return a spec or None."""
        return self._specs.get(name)

    def invoke(self, request: ToolRequest) -> ToolObservation:
        """Run the pipeline. Schema/permission failures never execute the handler."""
        started = time.perf_counter()
        spec = self._specs.get(request.tool)
        if spec is None:
            obs = _observation(
                ok=False,
                code="not_found",
                summary=f"Unknown tool: {request.tool}",
                tool=request.tool,
                kind="read",
                risk_class="low",
            )
            self._audit("tool_use", request, spec=None)
            self._audit("tool_result", request, spec=None, observation=obs)
            return _with_duration(obs, started)

        self._audit("tool_use", request, spec=spec)

        validated, err = _validate_args(spec, request.args)
        if err is not None:
            obs = _observation(
                ok=False,
                code="schema_invalid",
                summary=err,
                tool=spec.name,
                kind=spec.kind,
                risk_class=spec.risk_class,
            )
            self._audit("tool_result", request, spec=spec, observation=obs)
            return _with_duration(obs, started)

        perm = _permission_denied(self, spec, request, validated)
        if perm is not None:
            self._audit("tool_result", request, spec=spec, observation=perm)
            return _with_duration(perm, started)

        kind = _effective_kind(spec, validated)
        if kind == "irreversible" and not _irreversible_ok(self, request):
            obs = _observation(
                ok=False,
                code="gated",
                summary=(
                    f"Tool {spec.name!r} is irreversible and requires a human "
                    "or profile policy token; first suggestion is not enough."
                ),
                tool=spec.name,
                kind="irreversible",
                risk_class=spec.risk_class,
                detail={"confirm_insufficient": True},
            )
            self._audit("tool_result", request, spec=spec, observation=obs)
            return _with_duration(obs, started)

        try:
            obs = self._execute(spec, kind, validated, request)
        except (ValueError, OSError, FileNotFoundError, PermissionError) as exc:
            obs = _observation(
                ok=False,
                code="validation_failed",
                summary=str(exc)[:SUMMARY_MAX_CHARS],
                tool=spec.name,
                kind=kind,
                risk_class=spec.risk_class,
            )
        except Exception as exc:  # noqa: BLE001 — bus must always return an observation
            logger.exception("toolbus_handler_error", tool=spec.name, error=str(exc))
            obs = _observation(
                ok=False,
                code="error",
                summary=f"Tool error: {exc}"[:SUMMARY_MAX_CHARS],
                tool=spec.name,
                kind=kind,
                risk_class=spec.risk_class,
            )

        obs = _cap_summary(obs)
        obs = obs.model_copy(
            update={
                "tool": spec.name,
                "kind": kind,
                "risk_class": spec.risk_class,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            }
        )
        self._audit("tool_result", request, spec=spec, observation=obs)
        return obs

    def _execute(
        self,
        spec: ToolSpec,
        kind: ToolKind,
        args: dict[str, Any],
        request: ToolRequest,
    ) -> ToolObservation:
        if kind == "write" and spec.name != "commit_write" and _draft_on():
            return self._draft_write(spec, args, request)
        return spec.handler(args, request)

    def _draft_write(
        self,
        spec: ToolSpec,
        args: dict[str, Any],
        request: ToolRequest,
    ) -> ToolObservation:
        from ai_team.config.settings import get_workspace_dir
        from ai_team.tools.draft import commit_draft, stage_draft

        path = str(args.get("path") or args.get("file_path") or "")
        content = args.get("content")
        if not path or content is None:
            # Tools that write without a path/content pair (e.g. create_directory)
            # execute live; they are not file-body writes.
            return spec.handler(args, request)
        workspace = Path(get_workspace_dir())
        record = stage_draft(
            workspace,
            path,
            str(content),
            agent_role=request.agent_role,
            phase=request.phase,
        )
        if request.auto_commit or request.agent_role == "_harness":
            committed = commit_draft(workspace, record.draft_id)
            return _observation(
                ok=True,
                code="ok",
                summary=f"Wrote {committed} (harness commit).",
                tool=spec.name,
                kind="write",
                risk_class=spec.risk_class,
                artifact_refs=[committed],
                detail={"draft_id": record.draft_id, "auto_commit": True},
            )
        return _observation(
            ok=True,
            code="drafted",
            summary=f"Drafted {path}; call commit_write to promote.",
            tool=spec.name,
            kind="write",
            risk_class=spec.risk_class,
            artifact_refs=[f".harness/drafts/{record.draft_id}"],
            detail={"draft_id": record.draft_id, "intended_path": path},
        )

    def spans(self) -> list[dict[str, Any]]:
        """In-memory audit spans for this bus instance (tests + receipts)."""
        return list(self._spans)

    def _audit(
        self,
        event: str,
        request: ToolRequest,
        *,
        spec: ToolSpec | None,
        observation: ToolObservation | None = None,
    ) -> None:
        row: dict[str, Any] = {
            "type": event,
            "timestamp": datetime.now(UTC).isoformat(),
            "tool": request.tool,
            "tool_name": request.tool,
            "phase": request.phase,
            "agent_role": request.agent_role,
            "run_id": request.run_id,
            "backend": request.backend,
            "kind": spec.kind if spec else None,
            "risk_class": spec.risk_class if spec else None,
        }
        if observation is not None:
            row["ok"] = observation.ok
            row["code"] = observation.code
            row["result"] = observation.code
            row["summary"] = observation.summary
            row["artifact_refs"] = observation.artifact_refs
        self._spans.append(row)
        logger.info("toolbus_span", **{k: v for k, v in row.items() if k != "summary"})
        _append_audit_jsonl(row)
        _append_journal_event(row, observation)


_bus_var: contextvars.ContextVar[ToolBus | None] = contextvars.ContextVar(
    "ai_team_tool_bus", default=None
)


def get_bus() -> ToolBus:
    """Return the process/context ToolBus, registering builtins on first use."""
    bus = _bus_var.get()
    if bus is None:
        bus = ToolBus()
        from ai_team.tools.catalog import register_builtin_tools

        register_builtin_tools(bus)
        _bus_var.set(bus)
    return bus


def reset_bus(*, empty: bool = False) -> ToolBus:
    """Replace the context bus. Used by tests. Not a cross-run singleton."""
    bus = ToolBus()
    if not empty:
        from ai_team.tools.catalog import register_builtin_tools

        register_builtin_tools(bus)
    _bus_var.set(bus)
    return bus


def observation_to_agent_text(obs: ToolObservation) -> str:
    """Stringify an observation for frameworks that require a str tool result.

    Never dumps raw stdout as the sole content. Artifact refs are listed.
    """
    parts = [obs.summary]
    if obs.artifact_refs:
        parts.append("artifacts: " + ", ".join(obs.artifact_refs))
    text = "\n".join(parts)
    if len(text) > SUMMARY_MAX_CHARS:
        return text[: SUMMARY_MAX_CHARS - 1] + "…"
    return text


def _validate_args(spec: ToolSpec, args: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    try:
        model = spec.args_schema.model_validate(args)
    except ValidationError as exc:
        return {}, f"schema_invalid: {exc.error_count()} error(s)"
    return model.model_dump(), None


def _permission_denied(
    bus: ToolBus,
    spec: ToolSpec,
    request: ToolRequest,
    args: dict[str, Any],
) -> ToolObservation | None:
    if (
        spec.allow_roles
        and request.agent_role
        and request.agent_role not in spec.allow_roles
        and request.agent_role != "_harness"
    ):
        return _observation(
            ok=False,
            code="permission_denied",
            summary=f"Role {request.agent_role!r} may not call {spec.name}.",
            tool=spec.name,
            kind=spec.kind,
            risk_class=spec.risk_class,
        )
    _ = bus
    _ = args
    return None


def _effective_kind(spec: ToolSpec, args: dict[str, Any]) -> ToolKind:
    if spec.kind == "irreversible":
        return "irreversible"
    path = str(args.get("path") or args.get("file_path") or "")
    name = Path(path).name.lower()
    if name in {p.lower() for p in LOCKFILE_PATHS}:
        return "irreversible"
    return spec.kind


def _irreversible_ok(bus: ToolBus, request: ToolRequest) -> bool:
    from ai_team.tools.draft import irreversible_allowed_from_env

    return bool(
        request.allow_irreversible
        or request.human_approved
        or bus.allow_irreversible
        or irreversible_allowed_from_env()
    )


def _draft_on() -> bool:
    from ai_team.tools.draft import draft_writes_enabled

    return draft_writes_enabled()


def _observation(
    *,
    ok: bool,
    code: ObservationCode,
    summary: str,
    tool: str,
    kind: ToolKind,
    risk_class: RiskClass,
    artifact_refs: list[str] | None = None,
    detail: dict[str, Any] | None = None,
) -> ToolObservation:
    return ToolObservation(
        ok=ok,
        code=code,
        summary=summary[:SUMMARY_MAX_CHARS],
        artifact_refs=artifact_refs or [],
        tool=tool,
        kind=kind,
        risk_class=risk_class,
        duration_ms=0,
        detail=detail or {},
    )


def _with_duration(obs: ToolObservation, started: float) -> ToolObservation:
    return obs.model_copy(update={"duration_ms": int((time.perf_counter() - started) * 1000)})


def _cap_summary(obs: ToolObservation) -> ToolObservation:
    if len(obs.summary) <= SUMMARY_MAX_CHARS:
        return obs
    spilled = obs.summary
    refs = list(obs.artifact_refs)
    detail = dict(obs.detail)
    detail["summary_truncated"] = True
    detail["full_summary_chars"] = len(spilled)
    refs.append("summary://truncated")
    return obs.model_copy(
        update={
            "summary": spilled[: SUMMARY_MAX_CHARS - 1] + "…",
            "artifact_refs": refs,
            "detail": detail,
        }
    )


def _append_audit_jsonl(row: dict[str, Any]) -> None:
    """Best-effort append to workspace ``logs/audit.jsonl`` for TraceBuilder."""
    try:
        from ai_team.config.settings import get_workspace_dir

        logs = Path(get_workspace_dir()) / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        path = logs / "audit.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except (OSError, RuntimeError):
        logger.debug("toolbus_audit_jsonl_skipped")


def _append_journal_event(row: dict[str, Any], observation: ToolObservation | None) -> None:
    """Mirror tool spans into reconstructable ``logs/journal.jsonl`` (FM-008)."""
    try:
        from ai_team.config.settings import get_workspace_dir
        from ai_team.harness.journal import (
            JournalEvent,
            append_journal_event,
            constraint_pin_hash_for,
        )

        workspace = Path(get_workspace_dir())
        code = (observation.code if observation else row.get("code")) or ""
        if observation is not None and observation.ok:
            decision: str = "allow"
        elif code in {"permission_denied", "irreversible_blocked"}:
            decision = "deny"
        elif observation is not None and not observation.ok:
            decision = "error"
        else:
            decision = "info"
        spend_delta = None
        detail = observation.detail if observation else {}
        if isinstance(detail, dict) and isinstance(detail.get("spend_delta_usd"), int | float):
            spend_delta = float(detail["spend_delta_usd"])
        append_journal_event(
            workspace,
            JournalEvent(
                event=str(row.get("type") or "tool"),
                backend=row.get("backend"),
                phase=row.get("phase"),
                tool=row.get("tool"),
                decision=decision,  # type: ignore[arg-type]
                spend_delta_usd=spend_delta,
                constraint_pin_hash=constraint_pin_hash_for(workspace),
                run_id=row.get("run_id"),
                agent_role=row.get("agent_role"),
                detail={"code": code} if code else {},
            ),
        )
    except (OSError, RuntimeError, ValueError):
        logger.debug("toolbus_journal_jsonl_skipped")
