"""Unit tests for Claude MCP server wiring (no live subprocess)."""

from __future__ import annotations

import json
from pathlib import Path

from ai_team.backends.claude_agent_sdk_backend.tools.mcp_server import (
    build_ai_team_mcp_server,
    build_ai_team_mcp_tools,
)
from ai_team.backends.claude_agent_sdk_backend.tools.permissions import (
    MCP_RUN_APP_SMOKE,
    MCP_SERVER_KEY,
    devops_allowed_tools,
    get_disallowed_tools_for_yaml_role,
    qa_allowed_tools,
)


def test_get_disallowed_tools_for_yaml_role() -> None:
    assert "Bash" in get_disallowed_tools_for_yaml_role("product_owner")
    assert "Bash" in get_disallowed_tools_for_yaml_role("architect")
    assert get_disallowed_tools_for_yaml_role("manager") == []


def test_run_app_smoke_tool_registered(tmp_path: Path) -> None:
    tools = build_ai_team_mcp_tools(tmp_path)
    names = {getattr(t, "name", None) for t in tools}
    assert "run_app_smoke" in names


def test_run_app_smoke_in_qa_and_devops_allowlists() -> None:
    # Both QA (testing) and DevOps (deployment) phases must be able to smoke the app.
    assert MCP_RUN_APP_SMOKE in qa_allowed_tools()
    assert MCP_RUN_APP_SMOKE in devops_allowed_tools()


async def test_run_app_smoke_tool_skips_when_no_entrypoint(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    tools = build_ai_team_mcp_tools(tmp_path)
    smoke = next(t for t in tools if getattr(t, "name", None) == "run_app_smoke")
    out = await smoke.handler({})
    payload = json.loads(out["content"][0]["text"])
    # No bootable entrypoint -> skipped, and a skip is not an error.
    assert payload["ran"] is False
    assert out.get("is_error") is False


def test_build_ai_team_mcp_server_sdk_config(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    server = build_ai_team_mcp_server(ws)
    assert isinstance(server, dict)
    assert server.get("type") == "sdk"
    assert server.get("name") == MCP_SERVER_KEY
    assert server.get("instance") is not None
