"""Integration-style tests with mocked Claude SDK ``query()`` (no API calls)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from ai_team.backends.claude_agent_sdk_backend.backend import ClaudeAgentBackend
from ai_team.core.team_profile import TeamProfile
from claude_agent_sdk import ResultMessage


def test_claude_backend_run_collects_workspace_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-dummy")
    workspace = tmp_path / "ws"
    workspace.mkdir()

    async def fake_run(*_a: object, **_k: object) -> ResultMessage:
        return ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="sess-integ",
            total_cost_usd=0.01,
            usage={"input_tokens": 1},
        )

    profile = TeamProfile(
        name="proto",
        agents=["architect", "fullstack_developer", "qa_engineer"],
        phases=["planning", "development", "testing"],
    )

    with patch(
        "ai_team.backends.claude_agent_sdk_backend.backend.run_orchestrator",
        new=fake_run,
    ):
        backend = ClaudeAgentBackend()
        pr = backend.run(
            "Build a tiny CLI",
            profile,
            workspace_dir=str(workspace),
        )

    assert pr.backend_name == "claude-agent-sdk"
    assert pr.success is True
    assert pr.raw.get("session_id") == "sess-integ"
    docs = workspace / "docs"
    assert docs.is_dir()
