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

        import os

        if os.environ.get("AI_TEAM_DENY_NATIVE_TOOLS", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        } and tool_name in ("Write", "Edit", "MultiEdit", "Bash"):
            return _deny(
                f"Native {tool_name} bypasses ToolBus; use MCP write_workspace_file / execute via bus"
            )

        if tool_name in ("Write", "Edit", "MultiEdit"):
            fp = str(tool_input.get("file_path", ""))
            lower = fp.lower()
            if ".." in fp or "/../" in fp or "\\..\\" in fp:
                return _deny(f"Blocked path traversal in {fp!r}")
            if any(s in lower for s in _SENSITIVE_SUBSTR):
                return _deny(f"Blocked write to sensitive path: {fp}")
            from ai_team.harness.acceptance import is_acceptance_target

            if is_acceptance_target(workspace, fp):
                return _deny(
                    "ACCEPTANCE.json is harness-owned; use MCP "
                    "mcp__ai_team_tools__acceptance_mark_passing to record a pass"
                )
            contract_deny = _contract_src_deny(workspace, fp)
            if contract_deny:
                return contract_deny

        if tool_name == "Bash":
            cmd = str(tool_input.get("command", ""))
            lower_cmd = cmd.lower()
            if "rm -rf /" in lower_cmd or "eval(" in cmd or "exec(" in cmd:
                return _deny("Blocked dangerous shell pattern")
            if any(p in lower_cmd for p in _SUBSHELL_PIPE):
                return _deny("Blocked pipe to shell")
            from ai_team.backends.claude_agent_sdk_backend.hooks.bash_parser import (
                extract_commands,
            )

            parsed = extract_commands(cmd)
            if not parsed.ok:
                return _deny(f"Blocked undecomposable or dangerous bash: {parsed.reason}")
            allow_deny = _bash_allowlist_deny(cmd, parsed)
            if allow_deny:
                return allow_deny

        _ = workspace.resolve()  # reserved for future cwd-bound checks
        return {}

    return security_pre_tool


def _contract_src_deny(workspace: Path, file_path: str) -> HookJSONOutput | None:
    """Deny ``src/`` writes without an accepted contract when the gate is on."""
    from ai_team.harness.contracts import accepted_covers_path, contract_gate_enabled

    if not contract_gate_enabled():
        return None
    rel = file_path.replace("\\", "/").lstrip("./")
    if "/src/" not in f"/{rel}" and not rel.startswith("src/"):
        return None
    if accepted_covers_path(workspace, rel):
        return None
    return _deny("src/ writes require an accepted build contract; negotiate first")


def _bash_allowlist_deny(command: str, parsed: object) -> HookJSONOutput | None:
    """Evaluate the per-role allowlist *after* deny patterns (off by default)."""
    import os

    from ai_team.backends.claude_agent_sdk_backend.hooks.bash_parser import ParseResult
    from ai_team.backends.claude_agent_sdk_backend.tools.permissions import (
        bash_allowlist_enabled,
        bash_command_permitted,
    )

    del command
    if not bash_allowlist_enabled():
        return None
    if not isinstance(parsed, ParseResult):
        return None
    role = os.environ.get("AI_TEAM_BASH_ROLE", "developer")
    for cmd in parsed.commands:
        if not bash_command_permitted(role, cmd.name):
            return _deny(f"bash command {cmd.name!r} is not on the {role} allowlist")
    return None


def _deny(reason: str) -> HookJSONOutput:
    logger.warning("claude_sdk_security_hook_deny", reason=reason)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
