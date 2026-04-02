"""Unit tests for Claude MCP server wiring (no live subprocess)."""

from __future__ import annotations

from pathlib import Path

from ai_team.backends.claude_agent_sdk_backend.tools.mcp_server import build_ai_team_mcp_server
from ai_team.backends.claude_agent_sdk_backend.tools.permissions import (
    MCP_SERVER_KEY,
    get_disallowed_tools_for_yaml_role,
)


def test_get_disallowed_tools_for_yaml_role() -> None:
    assert "Bash" in get_disallowed_tools_for_yaml_role("product_owner")
    assert "Bash" in get_disallowed_tools_for_yaml_role("architect")
    assert get_disallowed_tools_for_yaml_role("manager") == []


def test_build_ai_team_mcp_server_sdk_config(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    server = build_ai_team_mcp_server(ws)
    assert isinstance(server, dict)
    assert server.get("type") == "sdk"
    assert server.get("name") == MCP_SERVER_KEY
    assert server.get("instance") is not None
