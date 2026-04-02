"""Unit tests for ``developer_tools`` (common, backend, frontend, fullstack factories)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ai_team.tools.developer_tools import (
    ApiClientGeneratorTool,
    ApiImplementationTool,
    CodeGenerationTool,
    CodeReviewerTool,
    ComponentGeneratorTool,
    DatabaseSchemaDesignTool,
    DependencyResolverTool,
    FileWriterTool,
    OrmGeneratorTool,
    StateManagementTool,
    get_backend_developer_tools,
    get_developer_common_tools,
    get_frontend_developer_tools,
    get_fullstack_developer_tools,
)
from crewai.tools import BaseTool


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Isolated workspace + output with ``file_tools.get_settings`` patched."""
    workspace = tmp_path / "workspace"
    output = tmp_path / "output"
    workspace.mkdir()
    output.mkdir()
    mock_settings = MagicMock()
    mock_settings.project.workspace_dir = str(workspace)
    mock_settings.project.output_dir = str(output)
    mock_settings.guardrails.max_file_size_kb = 500
    mock_settings.guardrails.dangerous_patterns = [
        "eval(",
        "exec(",
        "__import__",
        "os.system",
        "subprocess.call",
    ]
    mock_settings.guardrails.pii_patterns = []
    with patch("ai_team.tools.file_tools.get_settings", return_value=mock_settings):
        yield workspace


class TestCommonDeveloperTools:
    def test_code_generation_returns_stub_message(self) -> None:
        out = CodeGenerationTool().run(
            prompt="Implement a health check",
            language="python",
            context="FastAPI",
        )
        assert "[code_generation]" in out
        assert "Tool stub" in out

    def test_dependency_resolver_returns_stub_message(self) -> None:
        out = DependencyResolverTool().run(
            manifest_path="requirements.txt",
            dependency_name="httpx",
            action="add",
        )
        assert "[dependency_resolver]" in out

    def test_code_reviewer_returns_stub_message(self) -> None:
        out = CodeReviewerTool().run(code="def f(): pass", focus="style")
        assert "[code_reviewer]" in out

    def test_file_writer_ok_writes_under_workspace(self, tmp_workspace: Path) -> None:
        out = FileWriterTool().run(path="src/hello.py", content="# hello", overwrite=False)
        assert out == "OK"
        assert (tmp_workspace / "src" / "hello.py").read_text(encoding="utf-8") == "# hello"

    def test_file_writer_returns_error_string_on_rejection(self, tmp_workspace: Path) -> None:
        with patch(
            "ai_team.tools.developer_tools.safe_write_file",
            side_effect=ValueError("Path traversal"),
        ):
            out = FileWriterTool().run(path="x.py", content="y")
        assert out.startswith("ERROR:")
        assert "traversal" in out


class TestBackendDeveloperTools:
    def test_database_schema_design_stub(self) -> None:
        out = DatabaseSchemaDesignTool().run(requirements="User has orders", dialect="postgresql")
        assert "[database_schema_design]" in out

    def test_api_implementation_stub(self) -> None:
        out = ApiImplementationTool().run(spec="GET /items", framework="fastapi")
        assert "[api_implementation]" in out

    def test_orm_generator_stub(self) -> None:
        out = OrmGeneratorTool().run(schema_or_entities="User(id)", orm="sqlalchemy")
        assert "[orm_generator]" in out


class TestFrontendDeveloperTools:
    def test_component_generator_stub(self) -> None:
        out = ComponentGeneratorTool().run(description="Login form", framework="react")
        assert "[component_generator]" in out

    def test_state_management_stub(self) -> None:
        out = StateManagementTool().run(requirement="global cart", library="zustand")
        assert "[state_management]" in out

    def test_api_client_generator_stub(self) -> None:
        out = ApiClientGeneratorTool().run(base_url_or_spec="http://localhost:8000")
        assert "[api_client_generator]" in out


class TestToolFactories:
    def test_get_developer_common_tools(self) -> None:
        tools = get_developer_common_tools()
        assert len(tools) == 4
        names = {t.name for t in tools}
        assert names == {"code_generation", "file_writer", "dependency_resolver", "code_reviewer"}
        assert all(isinstance(t, BaseTool) for t in tools)

    def test_get_backend_developer_tools(self) -> None:
        tools = get_backend_developer_tools()
        assert len(tools) == 3
        names = {t.name for t in tools}
        assert names == {"database_schema_design", "api_implementation", "orm_generator"}

    def test_get_frontend_developer_tools(self) -> None:
        tools = get_frontend_developer_tools()
        assert len(tools) == 3
        names = {t.name for t in tools}
        assert names == {"component_generator", "state_management", "api_client_generator"}

    def test_get_fullstack_developer_tools_combines_all(self) -> None:
        tools = get_fullstack_developer_tools()
        assert len(tools) == 10
        names = [t.name for t in tools]
        assert names[:4] == [
            "code_generation",
            "file_writer",
            "dependency_resolver",
            "code_reviewer",
        ]
        assert "database_schema_design" in names
        assert "component_generator" in names
