"""Unit tests for Claude MCP server wiring (no live subprocess)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ai_team.backends.claude_agent_sdk_backend.tools.mcp_server import (
    build_ai_team_mcp_server,
    build_ai_team_mcp_tools,
)
from ai_team.backends.claude_agent_sdk_backend.tools.permissions import (
    MCP_ACCEPTANCE_MARK_PASSING,
    MCP_ACCEPTANCE_STATUS,
    MCP_RUN_APP_SMOKE,
    MCP_RUN_UI_SMOKE,
    MCP_SERVER_KEY,
    architect_allowed_tools,
    developer_allowed_tools,
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


def test_run_ui_smoke_registered_and_qa_only(tmp_path: Path) -> None:
    names = {getattr(t, "name", None) for t in build_ai_team_mcp_tools(tmp_path)}
    assert "run_ui_smoke" in names
    assert MCP_RUN_UI_SMOKE in qa_allowed_tools()
    assert MCP_RUN_UI_SMOKE not in developer_allowed_tools()


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


def test_write_workspace_file_registered(tmp_path: Path) -> None:
    names = {getattr(t, "name", None) for t in build_ai_team_mcp_tools(tmp_path)}
    assert "write_workspace_file" in names


@pytest.mark.bus_draft
async def test_write_workspace_file_drafts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(tmp_path / "out"))
    (tmp_path / "out").mkdir()
    from ai_team.config.settings import reload_settings
    from ai_team.tools.bus import reset_bus

    reload_settings()
    reset_bus()
    tools = build_ai_team_mcp_tools(tmp_path)
    write = next(t for t in tools if getattr(t, "name", None) == "write_workspace_file")
    out = await write.handler({"path": "src/a.py", "content": "x = 1\n"})
    text = out["content"][0]["text"]
    assert "draft" in text.lower() or "Drafted" in text
    assert not (tmp_path / "src" / "a.py").exists()


async def test_validate_code_safety_and_guardrails_error_paths(tmp_path: Path) -> None:
    tools = {getattr(t, "name", None): t for t in build_ai_team_mcp_tools(tmp_path)}
    safe = await tools["validate_code_safety"].handler({"code": "x = 1"})
    assert safe.get("is_error") is not True
    bad = await tools["validate_code_safety"].handler({"code": "eval('1')"})
    assert bad.get("is_error") is True
    escaped = await tools["run_guardrails"].handler({"file_path": "../etc/passwd"})
    assert escaped.get("is_error") is True
    target = tmp_path / "src" / "ok.py"
    target.parent.mkdir()
    target.write_text("x = 1\n", encoding="utf-8")
    checked = await tools["run_guardrails"].handler(
        {"file_path": "src/ok.py", "check_types": ["path"]}
    )
    assert "path_security" in checked["content"][0]["text"]
    missing = await tools["run_guardrails"].handler(
        {"file_path": "src/missing.py", "check_types": ["code_safety"]}
    )
    assert missing.get("is_error") is True


async def test_acceptance_mcp_tools_persist_identity(tmp_path: Path) -> None:
    from ai_team.harness.acceptance import write_initial
    from ai_team.models.requirements import (
        AcceptanceCriterion,
        MoSCoW,
        RequirementsDocument,
        UserStory,
    )

    req = RequirementsDocument(
        project_name="todo",
        user_stories=[
            UserStory(
                as_a="user",
                i_want="list",
                so_that="see",
                acceptance_criteria=[AcceptanceCriterion(description="GET /todos 200")],
                priority=MoSCoW.MUST,
            )
        ],
    )
    doc = write_initial(tmp_path, req, "run-mcp")
    ev = tmp_path / "docs" / "smoke_results.json"
    ev.parent.mkdir()
    ev.write_text("{}", encoding="utf-8")
    tools = {getattr(t, "name", None): t for t in build_ai_team_mcp_tools(tmp_path)}
    assert MCP_ACCEPTANCE_STATUS in architect_allowed_tools()
    assert MCP_ACCEPTANCE_STATUS in developer_allowed_tools()
    assert MCP_ACCEPTANCE_STATUS in qa_allowed_tools()
    assert MCP_ACCEPTANCE_MARK_PASSING in qa_allowed_tools()
    assert MCP_ACCEPTANCE_MARK_PASSING not in developer_allowed_tools()

    missing = await tools["acceptance_status"].handler({})
    st = json.loads(missing["content"][0]["text"])
    assert st["total"] >= 1
    marked = await tools["acceptance_mark_passing"].handler(
        {
            "item_id": doc.items[0].id,
            "evidence": ["docs/smoke_results.json"],
            "verified_by": "qa_agent",
            "agent_role": "qa_engineer",
            "session_id": "sess-9",
            "subagent_id": "qa-sub",
        }
    )
    body = json.loads(marked["content"][0]["text"])
    assert body["ok"] is True
    assert body["identity"]["session_id"] == "sess-9"
    assert body["identity"]["subagent_id"] == "qa-sub"
    reject = await tools["acceptance_mark_passing"].handler(
        {"item_id": "nope", "evidence": [], "verified_by": "qa_agent"}
    )
    assert reject.get("is_error") is True
    bad_v = await tools["acceptance_mark_passing"].handler(
        {"item_id": "x", "evidence": ["a"], "verified_by": "friend"}
    )
    assert bad_v.get("is_error") is True


def test_acceptance_status_errors_when_missing(tmp_path: Path) -> None:
    async def _run() -> None:
        tools = {getattr(t, "name", None): t for t in build_ai_team_mcp_tools(tmp_path)}
        out = await tools["acceptance_status"].handler({})
        assert out.get("is_error") is True

    import asyncio

    asyncio.run(_run())
