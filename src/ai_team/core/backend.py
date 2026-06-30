"""Backend protocol: shared contract for CrewAI, LangGraph, and future orchestrators."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from ai_team.core.result import ProjectResult
from ai_team.core.stream_helpers import stream_via_threaded_run
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


class ThreadedBackend:
    """Mixin-style base providing default stream() via threaded ``run()``."""

    name: str

    def run(
        self,
        description: str,
        profile: TeamProfile,
        env: str | None = None,
        **kwargs: Any,
    ) -> ProjectResult:
        raise NotImplementedError

    async def stream(
        self,
        description: str,
        profile: TeamProfile,
        env: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        async for event in stream_via_threaded_run(
            backend_name=self.name,
            run_fn=self.run,
            description=description,
            profile=profile,
            env=env,
            **kwargs,
        ):
            yield event
