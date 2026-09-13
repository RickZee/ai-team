"""Crew-level memory toggle aligned with application settings."""

from __future__ import annotations


def crew_memory_enabled() -> bool:
    """Return whether CrewAI crew memory and embedder should be enabled."""
    try:
        from ai_team.config.settings import get_settings

        return get_settings().memory.memory_enabled
    except Exception:
        return False
