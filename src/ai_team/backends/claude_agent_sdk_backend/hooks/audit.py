"""Append-only audit log for tool lifecycle events."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from claude_agent_sdk.types import HookContext, HookInput, HookJSONOutput

logger = structlog.get_logger(__name__)


def build_audit_hook(log_path: Path) -> Any:
    """Log PreToolUse / PostToolUse events to JSONL."""

    async def audit_hook(
        inp: HookInput,
        _tool_use_id: str | None,
        _ctx: HookContext,
    ) -> HookJSONOutput:
        ev = str(inp.get("hook_event_name") or "")
        if ev not in {"PreToolUse", "PostToolUse"}:
            return {}
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": ev,
            "tool": inp.get("tool_name"),
            "session_id": inp.get("session_id"),
        }
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError as e:
            logger.warning("claude_audit_write_failed", error=str(e))
        return {}

    return audit_hook


def build_subagent_audit_hook(log_path: Path) -> Any:
    """Log SubagentStart / SubagentStop to the same JSONL audit stream."""

    async def subagent_hook(
        inp: HookInput,
        _tool_use_id: str | None,
        _ctx: HookContext,
    ) -> HookJSONOutput:
        ev = str(inp.get("hook_event_name") or "")
        if ev not in {"SubagentStart", "SubagentStop"}:
            return {}
        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": ev,
            "session_id": inp.get("session_id"),
            "agent_id": inp.get("agent_id"),
            "agent_type": inp.get("agent_type"),
        }
        if ev == "SubagentStop":
            entry["agent_transcript_path"] = inp.get("agent_transcript_path")
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError as e:
            logger.warning("claude_subagent_audit_write_failed", error=str(e))
        return {}

    return subagent_hook
