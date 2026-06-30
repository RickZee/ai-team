"""Shared async stream wrappers for threaded backend runs."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile


async def stream_via_threaded_run(
    *,
    backend_name: str,
    run_fn: Callable[..., ProjectResult],
    description: str,
    profile: TeamProfile,
    env: str | None = None,
    extra_started: dict[str, Any] | None = None,
    **kwargs: Any,
) -> AsyncIterator[dict[str, Any]]:
    """Yield run_started, execute ``run_fn`` in a thread pool, then run_finished."""
    started: dict[str, Any] = {
        "type": "run_started",
        "backend": backend_name,
        "team_profile": profile.name,
    }
    if extra_started:
        started.update(extra_started)
    yield started
    result = await asyncio.to_thread(run_fn, description, profile, env, **kwargs)
    yield {
        "type": "run_finished",
        "backend": backend_name,
        "success": result.success,
        "result": result.model_dump(mode="json"),
    }
