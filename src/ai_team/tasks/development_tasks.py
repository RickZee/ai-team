"""Deprecated import path. Removal: 2026-12-31 (v0.3.0)."""

from __future__ import annotations

from ai_team._compat import warn_moved

warn_moved(
    "ai_team.tasks.development_tasks", "ai_team.backends.crewai_backend.tasks.development_tasks"
)

from ai_team.backends.crewai_backend.tasks.development_tasks import *  # noqa: E402, F403
