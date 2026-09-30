"""Strands tool specs built from :class:`BridgedTool`.

The ``@tool`` decorator cannot take a runtime JSON schema, so this module
emits the module-level tool spec form.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ai_team.backends.common.tool_bridge import BridgedTool


def strands_tool_spec(tool: BridgedTool) -> dict[str, Any]:
    """Return a Strands tool spec dict for ``tool``."""
    schema = tool.json_schema or {"type": "object", "properties": {}}
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": {"json": schema},
    }


def strands_tool_callable(tool: BridgedTool) -> Callable[[dict[str, Any]], str]:
    """Return a handler that forwards arguments through the bridge."""

    def handler(tool_use: dict[str, Any] | None = None, **kwargs: Any) -> str:
        payload = dict(tool_use or {})
        payload.update(kwargs)
        return tool.call(payload)

    return handler
