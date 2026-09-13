"""Deprecated import path. Removal: 2026-12-31 (v0.3.0)."""

from __future__ import annotations

from ai_team._compat import warn_moved

warn_moved("ai_team.agents.qa_engineer", "ai_team.backends.crewai_backend.agents.qa_engineer")

from ai_team.backends.crewai_backend.agents.qa_engineer import *  # noqa: E402, F403
