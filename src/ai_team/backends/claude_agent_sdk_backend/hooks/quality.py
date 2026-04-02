"""PostToolUse hooks: warn on placeholder patterns in written Python."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from claude_agent_sdk.types import HookContext, HookInput, HookJSONOutput

_PLACEHOLDERS = ("TODO", "FIXME", "NotImplementedError", "pass  # implement")


def build_quality_post_tool_hook(workspace: Path) -> Any:
    """Return async PostToolUse hook for Write/Edit outputs."""

    async def quality_post_tool(
        inp: HookInput,
        _tool_use_id: str | None,
        _ctx: HookContext,
    ) -> HookJSONOutput:
        if inp.get("hook_event_name") != "PostToolUse":
            return {}
        tool_name = str(inp.get("tool_name") or "")
        if tool_name not in ("Write", "Edit", "MultiEdit"):
            return {}
        tool_input = inp.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            return {}
        fp = str(tool_input.get("file_path", ""))
        if not fp.endswith(".py"):
            if fp.endswith(".json"):
                return _json_hint(fp, inp.get("tool_response"))
            return {}

        text = _extract_written_text(inp.get("tool_response"))
        if not text:
            return {}
        found = [p for p in _PLACEHOLDERS if p in text]
        if not found:
            return {}
        return {
            "systemMessage": (
                f"Quality: {fp} may contain placeholders {found!r}. "
                "Replace with real implementations before finishing."
            ),
            "continue_": True,
        }

    return quality_post_tool


def _extract_written_text(tool_response: Any) -> str:
    if tool_response is None:
        return ""
    if isinstance(tool_response, str):
        return tool_response
    if isinstance(tool_response, dict):
        for key in ("content", "text", "stdout", "message"):
            v = tool_response.get(key)
            if isinstance(v, str):
                return v
    return str(tool_response)


def _json_hint(fp: str, tool_response: Any) -> HookJSONOutput:
    text = _extract_written_text(tool_response)
    if not text.strip():
        return {}
    try:
        json.loads(text)
    except json.JSONDecodeError as e:
        return {
            "systemMessage": f"JSON file {fp} may be invalid: {e}",
            "continue_": True,
        }
    return {}
