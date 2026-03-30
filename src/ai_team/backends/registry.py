"""Resolve orchestration backends by name."""

from __future__ import annotations

from ai_team.core.backend import Backend


def get_backend(name: str) -> Backend:
    """Return a backend instance for ``crewai`` or ``langgraph``."""
    key = (name or "crewai").strip().lower()
    if key == "crewai":
        from ai_team.backends.crewai_backend.backend import CrewAIBackend

        return CrewAIBackend()
    if key == "langgraph":
        from ai_team.backends.langgraph_backend.backend import LangGraphBackend

        return LangGraphBackend()
    msg = f"Unknown backend {name!r}. Use: crewai | langgraph"
    raise ValueError(msg)
