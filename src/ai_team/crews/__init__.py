"""Deprecated import path. Removal: 2026-12-31 (v0.3.0)."""

from __future__ import annotations

from ai_team._compat import warn_moved

warn_moved("ai_team.crews", "ai_team.backends.crewai_backend.crews")

from ai_team.backends.crewai_backend.crews import *  # noqa: E402, F403
