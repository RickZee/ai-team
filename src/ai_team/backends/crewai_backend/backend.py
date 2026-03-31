"""CrewAI implementation of the shared Backend protocol."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import structlog
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile
from ai_team.flows.main_flow import run_ai_team
from ai_team.monitor import TeamMonitor

logger = structlog.get_logger(__name__)


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

        try:
            payload = run_ai_team(
                _maybe_augment_with_rag(description),
                monitor=monitor,
                skip_estimate=bool(kwargs.get("skip_estimate", False)),
                env_override=env,
                complexity_override=kwargs.get("complexity_override"),
            )
            enriched = {
                **payload,
                "team_profile": profile.name,
                "agents": profile.agents,
                "phases": profile.phases,
            }
            return ProjectResult(
                backend_name=self.name,
                success=True,
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
