"""Agent Framework function tools built from :class:`BridgedTool`."""

from __future__ import annotations

from typing import Any

from ai_team.backends.common.tool_bridge import BridgedTool


def agent_framework_function_tool(tool: BridgedTool) -> dict[str, Any]:
    """Return a function-tool dict with an explicit JSON schema.

    The callable is the bridge. It returns observation text, including errors.
    """
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.json_schema or {"type": "object", "properties": {}},
        "func": tool.call,
    }
