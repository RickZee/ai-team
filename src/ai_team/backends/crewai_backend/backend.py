"""CrewAI implementation of the shared Backend protocol."""

from __future__ import annotations

import asyncio
import contextlib
import json
import multiprocessing
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import structlog
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile
from ai_team.flows.main_flow import run_ai_team
from ai_team.monitor import TeamMonitor
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

_CONSOLE_DISABLED = False
_DEVNULL_HANDLE: Any | None = None


def _disable_crewai_console() -> None:
    """Neutralize CrewAI Rich live console (required for eval subprocesses / non-TTY).

    crewai's EventListener singleton hardwires ConsoleFormatter(verbose=True).
    update_method_status() has no verbose gate and recurses into print() which
    calls rich.Live.update() — infinite mutual recursion in non-TTY subprocesses.
    Setting _is_streaming=True makes print() early-return on Tree args, breaking
    the cycle. verbose=False suppresses all other crew/task/agent rendering.
    """
    global _CONSOLE_DISABLED, _DEVNULL_HANDLE
    if _CONSOLE_DISABLED:
        return
    try:
        from crewai.events.event_listener import EventListener
        from rich.console import Console

        if _DEVNULL_HANDLE is None:
            _DEVNULL_HANDLE = open(os.devnull, "w")  # noqa: SIM115
        el = EventListener()
        el.formatter.verbose = False
        el.formatter._is_streaming = True
        el.formatter.console = Console(file=_DEVNULL_HANDLE, quiet=True)
        _CONSOLE_DISABLED = True
    except Exception as exc:
        logger.debug("crewai_console_disable_skipped", error=str(exc))


def _flatten_crewai_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe subset of ``run_ai_team`` output for eval/transport."""
    state_raw = payload.get("state")
    if isinstance(state_raw, dict):
        state_dict = state_raw
    elif isinstance(state_raw, BaseModel):
        state_dict = state_raw.model_dump(mode="json")
    else:
        state_dict = {}

    safe_state = {
        "project_id": state_dict.get("project_id"),
        "current_phase": state_dict.get("current_phase"),
        "generated_files": state_dict.get("generated_files") or [],
        "test_results": state_dict.get("test_results"),
        "phase_history": state_dict.get("phase_history") or [],
        "retry_counts": state_dict.get("retry_counts") or {},
        "metadata": state_dict.get("metadata") or {},
        "errors": state_dict.get("errors") or [],
    }
    project_id = safe_state.get("project_id")
    current_phase = safe_state.get("current_phase", "unknown")
    return {
        "state": safe_state,
        "project_id": project_id,
        "success": current_phase == "complete",
    }


def _run_crewai_subprocess(
    description: str,
    profile_name: str,
    kwargs: dict[str, Any],
    result_path: str,
) -> None:
    """Subprocess entry point: run the CrewAI flow and write a JSON result file.

    Runs in a fresh interpreter (multiprocessing "spawn"), so it must be
    self-contained — no closures, no objects captured from the parent. This
    is what makes the hard-kill in ``CrewAIBackend.stream`` actually work:
    CrewAI's Rich console / event-bus threads have been observed to deadlock
    and ignore in-process timeouts (SIGALRM swallowed by the same threads,
    see docs/journal/2026-06-28.md); an OS-level ``kill()`` on this whole
    process works regardless of what CrewAI's threads are doing.
    """
    import structlog as _structlog
    from ai_team.core.team_profile import load_team_profile
    from ai_team.flows.main_flow import run_ai_team
    from ai_team.monitor import TeamMonitor

    _logger = _structlog.get_logger(__name__)
    result: dict[str, Any]
    try:
        profile = load_team_profile(profile_name)
        monitor = TeamMonitor(project_name=description[:50])
        from ai_team.config.llm_observability import register_crewai_spend_guard
        from ai_team.core.spend_guard import current_spend, reset_spend_guard

        explicit_id = str(kwargs.get("thread_id") or kwargs.get("project_id") or "").strip() or None
        register_crewai_spend_guard()
        reset_spend_guard(kwargs.get("run_budget_usd"), run_id=explicit_id)
        _disable_crewai_console()

        from ai_team.config.settings import reload_settings, scoped_workspace_dir

        reload_settings()
        ws_override = kwargs.get("workspace_dir")
        ws_scope = (
            scoped_workspace_dir(str(ws_override)) if ws_override else contextlib.nullcontext()
        )
        with ws_scope:
            payload = run_ai_team(
                description,
                monitor=monitor,
                skip_estimate=bool(kwargs.get("skip_estimate", False)),
                env_override=kwargs.get("env"),
                complexity_override=kwargs.get("complexity_override"),
                team_profile=profile.name,
                verbose=kwargs.get("verbose", False),
                run_label=str(kwargs.get("run_label") or ""),
                project_id=explicit_id,
            )
        enriched = _flatten_crewai_payload(payload)
        enriched.update(
            {
                "team_profile": profile.name,
                "agents": profile.agents,
                "phases": profile.phases,
                # Spend lives in this subprocess only — report it in the result
                # file so the parent can surface real $ per run.
                "spend": current_spend(),
            }
        )
        result = {"success": bool(enriched.get("success")), "raw": enriched, "error": None}
    except Exception as e:  # noqa: BLE001 - must always write a result file
        _logger.exception("crewai_subprocess_run_failed", error=str(e))
        try:
            spend = current_spend()
        except Exception:
            spend = {}
        result = {"success": False, "raw": {"spend": spend}, "error": str(e)}

    Path(result_path).write_text(json.dumps(result, default=str), encoding="utf-8")


class CrewAIBackend:
    """Delegates to ``run_ai_team`` / ``AITeamFlow`` (existing CrewAI stack)."""

    name: str = "crewai"

    def run(
        self,
        description: str,
        profile: TeamProfile,
        env: str | None = None,
        **kwargs: Any,
    ) -> ProjectResult:
        """Execute the CrewAI flow; profile is recorded on the result for observability."""
        raw_monitor = kwargs.get("monitor")
        monitor: TeamMonitor | None = raw_monitor if isinstance(raw_monitor, TeamMonitor) else None
        if raw_monitor is not None and monitor is None:
            logger.warning(
                "crewai_backend_invalid_monitor_type",
                type_name=type(raw_monitor).__name__,
            )

        # Per-run spend ceiling: register the LiteLLM cost callback (idempotent)
        # and reset the budget so a runaway crash/retry loop is aborted.
        from ai_team.config.llm_observability import register_crewai_spend_guard
        from ai_team.core.spend_guard import reset_spend_guard

        register_crewai_spend_guard()
        reset_spend_guard(
            kwargs.get("run_budget_usd"),
            run_id=str(kwargs.get("thread_id") or kwargs.get("project_id") or "").strip() or None,
        )
        _disable_crewai_console()

        from ai_team.config.settings import reload_settings, scoped_workspace_dir

        reload_settings()

        # Scoped, not a bare os.environ write: a permanent mutation here leaks
        # this run's workspace into any later call in this process that
        # forgets to override it (see langgraph/claude-sdk backends for the
        # same fix — observed as stray workspace/<value>/ dirs accumulating
        # from a test that left PROJECT_WORKSPACE_DIR stuck).
        ws_override = kwargs.get("workspace_dir")
        ws_scope = (
            scoped_workspace_dir(str(ws_override)) if ws_override else contextlib.nullcontext()
        )
        with ws_scope:
            return self._run_scoped(description, profile, env, kwargs, monitor)

    def _run_scoped(
        self,
        description: str,
        profile: TeamProfile,
        env: str | None,
        kwargs: dict[str, Any],
        monitor: TeamMonitor | None,
    ) -> ProjectResult:
        try:
            explicit_id = (
                str(kwargs.get("thread_id") or kwargs.get("project_id") or "").strip() or None
            )
            payload = run_ai_team(
                description,
                monitor=monitor,
                skip_estimate=bool(kwargs.get("skip_estimate", False)),
                env_override=env,
                complexity_override=kwargs.get("complexity_override"),
                team_profile=profile.name,
                verbose=kwargs.get("verbose", False),
                run_label=str(kwargs.get("run_label") or ""),
                project_id=explicit_id,
            )
            enriched = _flatten_crewai_payload(payload)
            enriched.update(
                {
                    "team_profile": profile.name,
                    "agents": profile.agents,
                    "phases": profile.phases,
                }
            )
            return ProjectResult(
                backend_name=self.name,
                success=bool(enriched.get("success")),
                raw=enriched,
                team_profile=profile.name,
            )
        except Exception as e:
            logger.exception("crewai_backend_run_failed", error=str(e))
            return ProjectResult(
                backend_name=self.name,
                success=False,
                raw={},
                error=str(e),
                team_profile=profile.name,
            )

    async def stream(
        self,
        description: str,
        profile: TeamProfile,
        env: str | None = None,
        _subprocess_target: Any = None,
        _timeout_override_s: float | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the flow in a real OS subprocess with a hard wall-clock kill.

        CrewAI's Rich console / event-bus threads have been observed to
        deadlock inside their own retry-recovery path and to ignore an
        in-process timeout (see docs/journal/2026-06-28.md, docs/handoff-
        2026-07-01.md §9) — a hung Python *thread* can't be forcibly killed
        from outside, and while it spins it starves the whole process's GIL,
        stalling unrelated backends running concurrently (observed: a 78min
        delay in LangGraph's own HITL-interrupt detection during a 3-way
        Compare run caused entirely by CrewAI's hung thread, not a LangGraph
        bug). A subprocess can actually be killed, and doesn't share a GIL
        with the rest of the server.

        No live ``TeamMonitor`` streaming for this backend — the object
        can't cross a process boundary. The Compare column shows
        started -> finished/killed rather than granular phase updates;
        CrewAI is comparison-only, so this trade-off matches its status.

        ``_subprocess_target``/``_timeout_override_s`` are test-only hooks: a
        ``multiprocessing.Process`` target must be picklable-by-reference, so
        tests substitute a trivial top-level stub instead of mocking (mocks
        don't cross the spawn boundary into the child interpreter).
        """
        import tempfile

        from ai_team.config.settings import get_settings

        yield {"type": "run_started", "backend": self.name, "team_profile": profile.name}

        target = _subprocess_target or _run_crewai_subprocess
        timeout_s = (
            _timeout_override_s
            if _timeout_override_s is not None
            else get_settings().crewai.hard_timeout_seconds
        )
        with tempfile.TemporaryDirectory(prefix="crewai_result_") as tmpdir:
            result_path = os.path.join(tmpdir, "result.json")
            ctx = multiprocessing.get_context("spawn")
            proc = ctx.Process(
                target=target,
                args=(description, profile.name, dict(kwargs), result_path),
                daemon=True,
            )
            proc.start()
            deadline = time.monotonic() + timeout_s
            killed = False
            while proc.is_alive():
                if time.monotonic() > deadline:
                    killed = True
                    logger.warning(
                        "crewai_subprocess_hard_kill",
                        timeout_s=timeout_s,
                        pid=proc.pid,
                    )
                    proc.terminate()
                    await asyncio.sleep(2)
                    if proc.is_alive():
                        proc.kill()
                    break
                await asyncio.sleep(1)
            proc.join(timeout=10)

            if killed:
                result = ProjectResult(
                    backend_name=self.name,
                    success=False,
                    raw={},
                    error=f"crewai_hard_timeout: force-killed after {timeout_s}s wall-clock",
                    team_profile=profile.name,
                )
            else:
                try:
                    payload = json.loads(Path(result_path).read_text(encoding="utf-8"))
                    result = ProjectResult(
                        backend_name=self.name,
                        success=bool(payload.get("success")),
                        raw=payload.get("raw") or {},
                        error=payload.get("error"),
                        team_profile=profile.name,
                    )
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    logger.error("crewai_subprocess_result_unreadable", error=str(e))
                    result = ProjectResult(
                        backend_name=self.name,
                        success=False,
                        raw={},
                        error=f"crewai_subprocess_crashed: {e}",
                        team_profile=profile.name,
                    )

        yield {
            "type": "run_finished",
            "backend": self.name,
            "success": result.success,
            "result": result.model_dump(mode="json"),
        }
