"""Backend protocol: shared contract for CrewAI, LangGraph, and future orchestrators."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile


@runtime_checkable
class Backend(Protocol):
    """Orchestration backend: run a project description under a team profile."""

    name: str

    def run(
        self,
        description: str,
        profile: TeamProfile,
        env: str | None = None,
        **kwargs: Any,
    ) -> ProjectResult:
        """Execute the full pipeline and return a normalized result."""
        ...

    def stream(
        self,
        description: str,
        profile: TeamProfile,
        env: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream progress events (tokens, node updates, checkpoints)."""
        ...
