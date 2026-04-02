"""Unit tests for Claude Agent SDK PreToolUse / PostToolUse hooks."""

from __future__ import annotations

import asyncio
from pathlib import Path

from ai_team.backends.claude_agent_sdk_backend.hooks.audit import build_subagent_audit_hook
from ai_team.backends.claude_agent_sdk_backend.hooks.quality import build_quality_post_tool_hook
from ai_team.backends.claude_agent_sdk_backend.hooks.security import build_security_pre_tool_hook
from claude_agent_sdk.types import HookContext


def test_security_hook_blocks_traversal() -> None:
    hook = build_security_pre_tool_hook(Path("/tmp/ws"))
    inp = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "../.env"},
        "tool_use_id": "1",
        "session_id": "s",
        "transcript_path": "/t",
        "cwd": "/tmp",
    }
    ctx: HookContext = {"signal": None}

    async def _run() -> None:
        out = await hook(inp, "1", ctx)
        hso = out.get("hookSpecificOutput") or {}
        assert hso.get("permissionDecision") == "deny"

    asyncio.run(_run())


def test_quality_hook_warns_on_todo_in_python() -> None:
    hook = build_quality_post_tool_hook(Path("/tmp/ws"))
    inp = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "src/x.py"},
        "tool_response": "def f():\n    pass  # TODO fix",
        "tool_use_id": "1",
        "session_id": "s",
        "transcript_path": "/t",
        "cwd": "/tmp",
    }
    ctx: HookContext = {"signal": None}

    async def _run() -> None:
        out = await hook(inp, "1", ctx)
        assert "systemMessage" in out
        assert "TODO" in str(out["systemMessage"])

    asyncio.run(_run())


def test_subagent_audit_hook_writes_jsonl(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.jsonl"
    hook = build_subagent_audit_hook(log_path)
    inp = {
        "hook_event_name": "SubagentStart",
        "session_id": "s1",
        "agent_id": "a1",
        "agent_type": "explore",
        "transcript_path": "/t",
        "cwd": "/w",
    }
    ctx: HookContext = {"signal": None}

    async def _run() -> None:
        await hook(inp, None, ctx)

    asyncio.run(_run())
    data = log_path.read_text(encoding="utf-8").strip()
    assert "SubagentStart" in data
    assert "a1" in data
