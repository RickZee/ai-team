"""CrewAI implementation of the shared Backend protocol."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from typing import Any

import structlog
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile
from ai_team.flows.main_flow import run_ai_team
from ai_team.monitor import TeamMonitor
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


def _disable_crewai_console() -> None:
    """Neutralize CrewAI Rich live console (required for eval subprocesses / non-TTY).

    crewai's EventListener singleton hardwires ConsoleFormatter(verbose=True).
    update_method_status() has no verbose gate and recurses into print() which
    calls rich.Live.update() — infinite mutual recursion in non-TTY subprocesses.
    Setting _is_streaming=True makes print() early-return on Tree args, breaking
    the cycle. verbose=False suppresses all other crew/task/agent rendering.
    """
    try:
        from crewai.events.event_listener import EventListener
        from rich.console import Console

        el = EventListener()
        el.formatter.verbose = False
        el.formatter._is_streaming = True
        el.formatter.console = Console(file=open(os.devnull, "w"), quiet=True)  # noqa: SIM115
    except Exception:
        pass  # crewai not installed or API changed — non-fatal


_disable_crewai_console()


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


def _maybe_augment_with_rag(description: str) -> str:
    """Prepend RAG snippets when ``RAG_ENABLED`` is true (Phase 6)."""
    try:
        from ai_team.rag.config import get_rag_config
        from ai_team.rag.pipeline import get_rag_pipeline

        if not get_rag_config().enabled:
            return description
        pipe = get_rag_pipeline()
        hits = pipe.retrieve(description.strip(), top_k=get_rag_config().top_k)
        if not hits:
            return description
        ctx = pipe.format_context(hits)
        return f"{ctx}\n\n---\n\nProject description:\n{description}"
    except Exception as e:
        logger.warning("crewai_rag_augment_skipped", error=str(e))
        return description


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
        reset_spend_guard(kwargs.get("run_budget_usd"))
        _disable_crewai_console()

        from ai_team.config.settings import reload_settings

        reload_settings()

        try:
            ws_override = kwargs.get("workspace_dir")
            if ws_override:
                os.environ["PROJECT_WORKSPACE_DIR"] = str(ws_override)
            payload = run_ai_team(
                _maybe_augment_with_rag(description),
                monitor=monitor,
                skip_estimate=bool(kwargs.get("skip_estimate", False)),
                env_override=env,
                complexity_override=kwargs.get("complexity_override"),
                team_profile=profile.name,
                verbose=kwargs.get("verbose", False),
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
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield a start event, run synchronously in a thread pool, then a finish event."""
        yield {
            "type": "run_started",
            "backend": self.name,
            "team_profile": profile.name,
        }
        result = await asyncio.to_thread(self.run, description, profile, env, **kwargs)
        yield {
            "type": "run_finished",
            "backend": self.name,
            "success": result.success,
            "result": result.model_dump(),
        }
