"""The tool bridge matches today's role tool names."""

from __future__ import annotations

from ai_team.backends.agent_framework_backend.tools import agent_framework_function_tool
from ai_team.backends.common.roles import role_keys, system_prompt_for_role
from ai_team.backends.common.tool_bridge import bridged_tools_for_role
from ai_team.backends.langgraph_backend.agents.prompts import build_system_prompt
from ai_team.backends.langgraph_backend.agents.tools import get_langchain_tools_for_role
from ai_team.backends.strands_backend.tools import strands_tool_callable, strands_tool_spec


def test_bridged_names_match_langgraph() -> None:
    for role in role_keys():
        bridged = [tool.name for tool in bridged_tools_for_role(role)]
        current = [tool.name for tool in get_langchain_tools_for_role(role)]
        assert bridged == current


def test_system_prompts_match_langgraph() -> None:
    for role in role_keys():
        assert system_prompt_for_role(role) == build_system_prompt(role)


def test_adapters_return_text_not_exceptions() -> None:
    tool = bridged_tools_for_role("fullstack_developer")[0]
    spec = strands_tool_spec(tool)
    assert spec["name"] == tool.name
    assert "inputSchema" in spec
    text = strands_tool_callable(tool)({})
    assert isinstance(text, str)
    framework = agent_framework_function_tool(tool)
    assert framework["name"] == tool.name
    assert isinstance(framework["func"]({}), str)
