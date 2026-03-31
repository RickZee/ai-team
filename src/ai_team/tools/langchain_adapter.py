"""
Convert CrewAI tools (``@tool`` wrappers and ``BaseTool`` subclasses) to LangChain tools.

CrewAI and LangGraph expect ``langchain_core.tools.BaseTool``. This module wraps
existing implementations without duplicating security or business logic.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

import structlog
from langchain_core.tools import BaseTool as LangChainBaseTool
from langchain_core.tools import StructuredTool

logger = structlog.get_logger(__name__)


def _slug_tool_name(name: str) -> str:
    """Normalize tool name for LangChain (alphanumeric + underscore)."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip()).strip("_").lower()
    return s or "tool"


def _strip_crewai_description(description: str) -> str:
    """Use the human-readable part of CrewAI's auto-generated description."""
    if "Tool Description:" in description:
        return description.split("Tool Description:", 1)[-1].strip()
    return description.strip()


def crewai_tool_to_langchain(tool: Any) -> LangChainBaseTool:
    """
    Convert a CrewAI tool instance or an existing LangChain tool to LangChain ``BaseTool``.

    Supports:
    - ``langchain_core.tools.BaseTool`` (pass-through)
    - CrewAI ``Tool`` (function-backed, has ``func``)
    - CrewAI ``BaseTool`` subclasses (``_run`` + ``args_schema``)
    """
    if isinstance(tool, LangChainBaseTool):
        return tool

    from crewai.tools.base_tool import BaseTool as CrewAIBaseTool
    from crewai.tools.base_tool import Tool as CrewAITool

    if isinstance(tool, CrewAITool):
        desc = _strip_crewai_description(tool.description)
        return StructuredTool.from_function(
            coroutine=None,
            func=tool.func,
            name=_slug_tool_name(tool.name),
            description=desc,
            args_schema=tool.args_schema,
        )

    if isinstance(tool, CrewAIBaseTool):

        def _invoke(**kwargs: Any) -> Any:
            return tool._run(**kwargs)

        desc = _strip_crewai_description(tool.description)
        return StructuredTool.from_function(
            coroutine=None,
            func=_invoke,
            name=_slug_tool_name(tool.name),
            description=desc,
            args_schema=tool.args_schema,
        )

    msg = f"Unsupported tool type for LangChain conversion: {type(tool)}"
    raise TypeError(msg)


def to_langchain_tools(tools: Sequence[Any]) -> list[LangChainBaseTool]:
    """Convert a sequence of CrewAI tools to LangChain tools."""
    return [crewai_tool_to_langchain(t) for t in tools]
