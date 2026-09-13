"""Role tool-name guard and per-role bash allowlists (R14 / R17.5)."""

from __future__ import annotations

import pytest
from ai_team.backends.claude_agent_sdk_backend.tools.permissions import (
    MCP_RUN_UI_SMOKE,
    assert_role_tools_are_registered,
    bash_command_permitted,
    qa_allowed_tools,
)


def test_every_role_allowlist_references_registered_tools() -> None:
    assert_role_tools_are_registered()


def test_developer_pytest_blocked_for_architect() -> None:
    assert bash_command_permitted("developer", "pytest") is True
    assert bash_command_permitted("architect", "pytest") is False
    assert bash_command_permitted("architect", "git") is True


def test_run_ui_smoke_is_qa_only() -> None:
    assert MCP_RUN_UI_SMOKE in qa_allowed_tools()
    from ai_team.backends.claude_agent_sdk_backend.tools.permissions import (
        architect_allowed_tools,
        developer_allowed_tools,
    )

    assert MCP_RUN_UI_SMOKE not in developer_allowed_tools()
    assert MCP_RUN_UI_SMOKE not in architect_allowed_tools()


def test_deny_patterns_still_fire_before_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.backends.test_claude_sdk_security_hook_adversarial import _call, _is_deny

    monkeypatch.setenv("AI_TEAM_BASH_ALLOWLIST", "1")
    monkeypatch.setenv("AI_TEAM_BASH_ROLE", "developer")
    # Would be on the developer allowlist if it parsed as `pytest`, but the
    # deny / fail-closed layer must win first.
    assert _is_deny(_call("Bash", {"command": "rm -rf /"}))
