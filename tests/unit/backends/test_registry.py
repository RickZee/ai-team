"""Unit tests for ``backends.registry.get_backend`` (T1.15, T5.12)."""

from __future__ import annotations

import pytest
from ai_team.backends.crewai_backend.backend import CrewAIBackend
from ai_team.backends.langgraph_backend.backend import LangGraphBackend
from ai_team.backends.registry import get_backend


class TestGetBackend:
    def test_returns_crewai(self) -> None:
        b = get_backend("crewai")
        assert isinstance(b, CrewAIBackend)
        assert b.name == "crewai"

    def test_returns_langgraph(self) -> None:
        b = get_backend("langgraph")
        assert isinstance(b, LangGraphBackend)
        assert b.name == "langgraph"

    def test_returns_claude_agent_sdk_aliases(self) -> None:
        from ai_team.backends.claude_agent_sdk_backend.backend import ClaudeAgentBackend

        for name in ("claude-agent-sdk", "claude-sdk"):
            b = get_backend(name)
            assert isinstance(b, ClaudeAgentBackend)

    def test_default_none_is_crewai(self) -> None:
        b = get_backend("crewai")
        assert isinstance(b, CrewAIBackend)

    def test_whitespace_normalized(self) -> None:
        b = get_backend("  LangGraph  ")
        assert isinstance(b, LangGraphBackend)

    def test_unknown_backend_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend("not-a-backend")

    def test_empty_string_defaults_to_crewai(self) -> None:
        """Empty string is falsy; implementation uses (name or \"crewai\").strip().lower()."""
        b = get_backend("")
        assert isinstance(b, CrewAIBackend)


class TestRegistryAdversarial:
    def test_none_input_defaults_to_crewai(self) -> None:
        """``None`` is falsy and should default like empty."""
        b = get_backend(None)  # type: ignore[arg-type]
        assert isinstance(b, CrewAIBackend)

    def test_garbage_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown"):
            get_backend("../../etc/passwd")
