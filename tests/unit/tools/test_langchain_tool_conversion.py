"""Tests for CrewAI → LangChain tool conversion (Phase 2)."""

from __future__ import annotations

import pytest
from ai_team.backends.langgraph_backend.agents.prompts import (
    AgentPromptBundle,
    load_agent_prompt,
)
from ai_team.backends.langgraph_backend.agents.tools import get_langchain_tools_for_role
from ai_team.tools.architect_tools import architecture_designer, get_architect_tools
from ai_team.tools.developer_tools import CodeGenerationTool
from ai_team.tools.file_tools import get_file_tools
from ai_team.tools.langchain_adapter import crewai_tool_to_langchain, to_langchain_tools
from langchain_core.tools import BaseTool as LangChainBaseTool


def test_crewai_tool_to_langchain_function_tool() -> None:
    lc = crewai_tool_to_langchain(architecture_designer)
    assert isinstance(lc, LangChainBaseTool)
    out = lc.invoke(
        {"system_overview": "sys", "components_description": "comp"},
    )
    assert isinstance(out, str)
    assert "Architecture" in out or "architecture" in out.lower()


def test_crewai_tool_to_langchain_basetool_subclass() -> None:
    dev = CodeGenerationTool()
    lc = crewai_tool_to_langchain(dev)
    assert isinstance(lc, LangChainBaseTool)
    out = lc.invoke({"prompt": "hello", "language": None, "context": None})
    assert "stub" in out.lower() or "phase" in out.lower()


def test_to_langchain_tools_list() -> None:
    crew = get_architect_tools()
    lc_list = to_langchain_tools(crew)
    assert len(lc_list) == len(crew)
    assert all(isinstance(t, LangChainBaseTool) for t in lc_list)


def test_get_langchain_tools_for_role_each_known_role() -> None:
    for key in (
        "manager",
        "product_owner",
        "architect",
        "backend_developer",
        "frontend_developer",
        "fullstack_developer",
        "devops_engineer",
        "cloud_engineer",
        "qa_engineer",
    ):
        tools = get_langchain_tools_for_role(key)
        assert len(tools) >= 1
        assert all(isinstance(t, LangChainBaseTool) for t in tools)


def test_get_langchain_tools_unknown_role() -> None:
    with pytest.raises(KeyError, match="Unknown role"):
        get_langchain_tools_for_role("not_a_real_role_xyz")


def test_load_agent_prompt_manager() -> None:
    bundle = load_agent_prompt("manager")
    assert isinstance(bundle, AgentPromptBundle)
    assert bundle.role_key == "manager"
    assert "Manager" in bundle.role or "manager" in bundle.role.lower()
    text = bundle.system_message()
    assert "Goal" in text
    assert "Background" in text


def test_file_tools_convert_and_invoke(tmp_path, monkeypatch) -> None:
    """File tools use workspace from settings; point workspace at tmp_path."""
    from ai_team.config.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings.project, "workspace_dir", str(tmp_path))
    monkeypatch.setattr(settings.project, "output_dir", str(tmp_path / "out"))
    (tmp_path / "out").mkdir(exist_ok=True)

    crew_file_tools = get_file_tools()
    assert crew_file_tools
    lc_tools = to_langchain_tools(crew_file_tools)
    write = next(t for t in lc_tools if "write" in t.name.lower())
    read = next(t for t in lc_tools if "read" in t.name.lower())
    write.invoke({"path": "hello.txt", "content": "test content"})
    content = read.invoke({"path": "hello.txt"})
    assert "test content" in content
