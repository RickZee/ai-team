"""Unit tests for Claude Agent SDK PreToolUse / PostToolUse hooks."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
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


def test_security_hook_denies_native_write_when_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_TEAM_DENY_NATIVE_TOOLS", "1")
    hook = build_security_pre_tool_hook(Path("/tmp/ws"))
    inp = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "src/ok.py"},
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
        assert "ToolBus" in str(hso.get("permissionDecisionReason") or "")

    asyncio.run(_run())


def _write_inp(workspace: Path, file_path: str, tool: str = "Write") -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"file_path": file_path},
        "tool_use_id": "1",
        "session_id": "s",
        "transcript_path": "/t",
        "cwd": str(workspace),
    }


@pytest.mark.parametrize("rel", ["ACCEPTANCE.json", "./ACCEPTANCE.json"])
def test_security_hook_denies_acceptance_relative_paths(tmp_path: Path, rel: str) -> None:
    (tmp_path / "ACCEPTANCE.json").write_text("{}", encoding="utf-8")
    hook = build_security_pre_tool_hook(tmp_path)
    ctx: HookContext = {"signal": None}

    async def _run() -> None:
        out = await hook(_write_inp(tmp_path, rel), "1", ctx)
        hso = out.get("hookSpecificOutput") or {}
        assert hso.get("permissionDecision") == "deny"
        assert "acceptance_mark_passing" in str(hso.get("permissionDecisionReason") or "")

    asyncio.run(_run())


def test_security_hook_denies_acceptance_absolute_and_symlink(tmp_path: Path) -> None:
    target = tmp_path / "ACCEPTANCE.json"
    target.write_text("{}", encoding="utf-8")
    alias = tmp_path / "docs"
    alias.mkdir()
    link = alias / "ACCEPTANCE.json"
    link.symlink_to(target)
    hook = build_security_pre_tool_hook(tmp_path)
    ctx: HookContext = {"signal": None}

    async def _run() -> None:
        for tool in ("Write", "Edit", "MultiEdit"):
            out = await hook(_write_inp(tmp_path, str(target), tool), "1", ctx)
            assert (out.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"
            out2 = await hook(_write_inp(tmp_path, str(link), tool), "1", ctx)
            assert (out2.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"

    asyncio.run(_run())


def test_security_hook_ignores_non_pretool(tmp_path: Path) -> None:
    hook = build_security_pre_tool_hook(tmp_path)
    ctx: HookContext = {"signal": None}

    async def _run() -> None:
        out = await hook({"hook_event_name": "PostToolUse", "tool_name": "Write"}, "1", ctx)
        assert out == {}

    asyncio.run(_run())


def test_quality_hook_covers_json_and_skip_paths(tmp_path: Path) -> None:
    hook = build_quality_post_tool_hook(tmp_path)
    ctx: HookContext = {"signal": None}

    async def _run() -> None:
        bad = await hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "docs/x.json"},
                "tool_response": "{not-json",
            },
            "1",
            ctx,
        )
        assert "invalid" in str(bad.get("systemMessage") or "").lower()
        good = await hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "docs/x.json"},
                "tool_response": "{}",
            },
            "1",
            ctx,
        )
        assert good == {}
        assert await hook({"hook_event_name": "PreToolUse", "tool_name": "Write"}, "1", ctx) == {}
        assert (
            await hook(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Bash",
                    "tool_input": {"command": "ls"},
                },
                "1",
                ctx,
            )
            == {}
        )
        assert (
            await hook(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Write",
                    "tool_input": {"file_path": "src/x.py"},
                    "tool_response": None,
                },
                "1",
                ctx,
            )
            == {}
        )
        assert (
            await hook(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Write",
                    "tool_input": {"file_path": "src/x.py"},
                    "tool_response": "def ok():\n    return 1\n",
                },
                "1",
                ctx,
            )
            == {}
        )
        assert (
            await hook(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Write",
                    "tool_input": {"file_path": "docs/x.md"},
                    "tool_response": "# hi",
                },
                "1",
                ctx,
            )
            == {}
        )
        assert (
            await hook(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Write",
                    "tool_input": "oops",
                },
                "1",
                ctx,
            )
            == {}
        )
        assert (
            await hook(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Write",
                    "tool_input": {"file_path": "docs/x.json"},
                    "tool_response": "   ",
                },
                "1",
                ctx,
            )
            == {}
        )
        from_dict = await hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": "src/y.py"},
                "tool_response": {"content": "TODO later"},
            },
            "1",
            ctx,
        )
        assert "TODO" in str(from_dict.get("systemMessage") or "")

    asyncio.run(_run())


def test_audit_hook_pre_post_and_unwritable(tmp_path: Path) -> None:
    from ai_team.backends.claude_agent_sdk_backend.hooks.audit import build_audit_hook

    log_path = tmp_path / "audit.jsonl"
    hook = build_audit_hook(log_path)
    ctx: HookContext = {"signal": None}

    async def _run() -> None:
        assert await hook({"hook_event_name": "Other"}, None, ctx) == {}
        await hook(
            {"hook_event_name": "PreToolUse", "tool_name": "Read", "session_id": "s"}, None, ctx
        )
        await hook(
            {"hook_event_name": "PostToolUse", "tool_name": "Read", "session_id": "s"}, None, ctx
        )
        assert len(log_path.read_text(encoding="utf-8").strip().splitlines()) == 2

    asyncio.run(_run())

    blocked = tmp_path / "blocked"
    blocked.write_text("x", encoding="utf-8")
    hook3 = build_audit_hook(blocked / "audit.jsonl")

    async def _blocked() -> None:
        out = await hook3({"hook_event_name": "PreToolUse", "tool_name": "Read"}, None, ctx)
        assert out == {}

    asyncio.run(_blocked())


def test_subagent_audit_stop_and_ignore(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.jsonl"
    hook = build_subagent_audit_hook(log_path)
    ctx: HookContext = {"signal": None}

    async def _run() -> None:
        assert await hook({"hook_event_name": "PreToolUse"}, None, ctx) == {}
        await hook(
            {
                "hook_event_name": "SubagentStop",
                "session_id": "s1",
                "agent_id": "a1",
                "agent_type": "qa",
                "agent_transcript_path": "/t",
            },
            None,
            ctx,
        )

    asyncio.run(_run())
    assert "SubagentStop" in log_path.read_text(encoding="utf-8")
