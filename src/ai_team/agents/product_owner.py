"""Deprecated import path. Removal: 2026-12-31 (v0.3.0)."""

from __future__ import annotations

from ai_team._compat import warn_moved

warn_moved("ai_team.agents.product_owner", "ai_team.backends.crewai_backend.agents.product_owner")

from ai_team.backends.crewai_backend.agents.product_owner import *  # noqa: E402, F403
