"""Smoke tests for Claude Agent SDK backend wiring."""

from __future__ import annotations

from ai_team.backends.claude_agent_sdk_backend.backend import ClaudeAgentBackend
from ai_team.backends.registry import get_backend


class TestClaudeAgentBackend:
    def test_get_backend_returns_instance(self) -> None:
        b = get_backend("claude-agent-sdk")
        assert isinstance(b, ClaudeAgentBackend)
        assert b.name == "claude-agent-sdk"
