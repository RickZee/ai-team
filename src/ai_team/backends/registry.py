"""Resolve orchestration backends by name."""

from __future__ import annotations

from ai_team.core.backend import Backend


def get_backend(name: str) -> Backend:
    """Return a backend instance for ``crewai``, ``langgraph``, or ``claude-agent-sdk``."""
    key = (name or "crewai").strip().lower()
    if key == "crewai":
        from ai_team.backends.crewai_backend.backend import CrewAIBackend

        return CrewAIBackend()
    if key == "langgraph":
        from ai_team.backends.langgraph_backend.backend import LangGraphBackend

        return LangGraphBackend()
    if key in ("claude-agent-sdk", "claude-sdk"):
        from ai_team.backends.claude_agent_sdk_backend.backend import ClaudeAgentBackend

        return ClaudeAgentBackend()
    msg = f"Unknown backend {name!r}. Use: crewai | langgraph | claude-agent-sdk"
    raise ValueError(msg)
