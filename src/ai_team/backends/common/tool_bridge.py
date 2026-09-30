"""Expose role tools as framework-neutral descriptors that call the ToolBus.

Exceptions from a tool become observation text. Frameworks never see a raise.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import structlog

from ai_team.backends.common.role_tools import crew_tools_for_role
from ai_team.tools.bus import get_bus, observation_to_agent_text
from ai_team.tools.kinds import ToolObservation, ToolRequest
from ai_team.tools.langchain_adapter import crewai_tool_to_langchain

logger = structlog.get_logger(__name__)

_BUS_ALIASES = {"file_writer": "write_file"}


@dataclass(frozen=True)
class BridgedTool:
    """One role tool: schema for the model, callable for the framework."""

    name: str
    description: str
    json_schema: dict[str, Any]
    call: Callable[[dict[str, Any]], str]


def _schema_of(tool: Any) -> dict[str, Any]:
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is None:
        return {"type": "object", "properties": {}}
    try:
        schema = args_schema.model_json_schema()
    except (AttributeError, TypeError, ValueError):
        return {"type": "object", "properties": {}}
    return schema if isinstance(schema, dict) else {"type": "object", "properties": {}}


def _bus_args(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "write_file":
        return {
            "path": str(payload.get("path") or ""),
            "content": str(payload.get("content") or ""),
        }
    return dict(payload)


def _underlying_for(tool: Any) -> Callable[..., Any]:
    def _underlying(**kwargs: Any) -> Any:
        return tool.invoke(kwargs)

    return _underlying


def _call_bus_or_underlying(
    name: str, underlying: Callable[..., Any]
) -> Callable[[dict[str, Any]], str]:
    def call(payload: dict[str, Any]) -> str:
        try:
            bus = get_bus()
            tool_name = _BUS_ALIASES.get(name, name)
            if bus.get_spec(tool_name) is not None:
                obs = bus.invoke(ToolRequest(tool=tool_name, args=_bus_args(tool_name, payload)))
                if isinstance(obs, ToolObservation):
                    return observation_to_agent_text(obs)
                return str(obs)
            result = underlying(**payload)
            return result if isinstance(result, str) else str(result)
        except (TypeError, ValueError, OSError, KeyError, RuntimeError) as exc:
            logger.info("bridged_tool_error", tool=name, error=str(exc))
            return f"error: {exc}"

    return call


def bridged_tools_for_role(role: str) -> list[BridgedTool]:
    """Bridge every tool that ``role`` has today.

    Names match the LangChain tools built from the same factories.
    """
    bridged: list[BridgedTool] = []
    for raw in crew_tools_for_role(role):
        langchain_tool = crewai_tool_to_langchain(raw)
        bridged.append(
            BridgedTool(
                name=langchain_tool.name,
                description=langchain_tool.description or "",
                json_schema=_schema_of(raw),
                call=_call_bus_or_underlying(langchain_tool.name, _underlying_for(langchain_tool)),
            )
        )
    return bridged
