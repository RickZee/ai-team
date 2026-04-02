"""PreToolUse hooks: block dangerous paths and shell patterns."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
from claude_agent_sdk.types import HookContext, HookInput, HookJSONOutput

logger = structlog.get_logger(__name__)

_SENSITIVE_SUBSTR = (".env", "credentials", "secrets", "id_rsa", ".pem")
_SUBSHELL_PIPE = ("| sh", "| bash", "| /bin/sh", "| /bin/bash")


def build_security_pre_tool_hook(
    workspace: Path,
) -> Any:
    """Return async PreToolUse hook callback."""

    async def security_pre_tool(
        inp: HookInput,
        _tool_use_id: str | None,
        _ctx: HookContext,
    ) -> HookJSONOutput:
        if inp.get("hook_event_name") != "PreToolUse":
            return {}
        tool_name = str(inp.get("tool_name") or "")
        tool_input = inp.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            tool_input = {}

        if tool_name in ("Write", "Edit", "MultiEdit"):
            fp = str(tool_input.get("file_path", ""))
            lower = fp.lower()
            if ".." in fp or "/../" in fp or "\\..\\" in fp:
                return _deny(f"Blocked path traversal in {fp!r}")
            if any(s in lower for s in _SENSITIVE_SUBSTR):
                return _deny(f"Blocked write to sensitive path: {fp}")

        if tool_name == "Bash":
            cmd = str(tool_input.get("command", ""))
            lower_cmd = cmd.lower()
            if "rm -rf /" in lower_cmd or "eval(" in cmd or "exec(" in cmd:
                return _deny("Blocked dangerous shell pattern")
            if any(p in lower_cmd for p in _SUBSHELL_PIPE):
                return _deny("Blocked pipe to shell")

        _ = workspace.resolve()  # reserved for future cwd-bound checks
        return {}

    return security_pre_tool


def _deny(reason: str) -> HookJSONOutput:
    logger.warning("claude_sdk_security_hook_deny", reason=reason)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
