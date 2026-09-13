"""Deprecated import path. Removal: 2026-12-31 (v0.3.0)."""

from __future__ import annotations

from ai_team._compat import warn_moved

warn_moved("ai_team.flows.main_flow", "ai_team.backends.crewai_backend.flows.main_flow")

from ai_team.backends.crewai_backend.flows.main_flow import *  # noqa: E402, F403
