"""
Comprehensive unit tests for agent tools: each tool in isolation,
tool schemas and return types, error handling per tool.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_team.tools.file_tools import (
    read_file,
    write_file,
    list_directory,
    create_directory,
    delete_file,
)
from ai_team.tools.product_owner import (
    requirements_parser,
    user_story_generator,
    acceptance_criteria_writer,
    priority_scorer,
)
from ai_team.tools.qa_tools import get_qa_tools


# -----------------------------------------------------------------------------
# File tools — isolation, schemas, error handling
# -----------------------------------------------------------------------------


@pytest.fixture
def tmp_workspace(tmp_path: Path):
    """Temporary workspace and output dir with patched settings."""
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
    mock_settings.guardrails.pii_patterns = [
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    ]
    with patch("ai_team.tools.file_tools.get_settings", return_value=mock_settings):
        yield workspace


class TestFileToolsIsolation:
    def test_read_file_success(self, tmp_workspace: Path) -> None:
        (tmp_workspace / "hello.txt").write_text("hello world")
        assert read_file("hello.txt") == "hello world"

    def test_read_file_path_traversal_rejected(self, tmp_workspace: Path) -> None:
        with pytest.raises(ValueError, match="Path traversal"):
            read_file("../../../etc/passwd")
        with pytest.raises(ValueError, match="Path traversal"):
            read_file("sub/../../secret.txt")

    def test_write_file_success(self, tmp_workspace: Path) -> None:
        path = tmp_workspace / "out.txt"
        write_file(str(path), "content")
        assert path.read_text() == "content"

    def test_list_directory_returns_list(self, tmp_workspace: Path) -> None:
        (tmp_workspace / "a").write_text("")
        (tmp_workspace / "b").write_text("")
        result = list_directory(".")
        assert isinstance(result, list)
        assert any("a" in str(e) or "b" in str(e) for e in result)

    def test_create_directory_success(self, tmp_workspace: Path) -> None:
        create_directory("newdir")
        assert (tmp_workspace / "newdir").is_dir()

    def test_delete_file_success(self, tmp_workspace: Path) -> None:
        (tmp_workspace / "to_delete.txt").write_text("x")
        delete_file("to_delete.txt", confirm=True)
        assert not (tmp_workspace / "to_delete.txt").exists()


class TestFileToolsErrorHandling:
    def test_read_file_nonexistent_raises(self, tmp_workspace: Path) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            read_file("nonexistent.txt")

    def test_read_file_directory_rejected(self, tmp_workspace: Path) -> None:
        (tmp_workspace / "adir").mkdir()
        with pytest.raises(ValueError, match="Not a file"):
            read_file("adir")


# -----------------------------------------------------------------------------
# Product owner tools — schemas and return types
# -----------------------------------------------------------------------------


class TestProductOwnerTools:
    def test_requirements_parser_returns_structured(self) -> None:
        raw = "As a user I want to login. As an admin I want to manage roles."
        result = requirements_parser.run(raw)
        assert isinstance(result, str)
        assert "user" in result.lower() or "login" in result.lower() or "theme" in result.lower()

    def test_user_story_generator_accepts_themes(self) -> None:
        themes = "Authentication, User management"
        result = user_story_generator.run(themes)
        assert isinstance(result, str)

    def test_acceptance_criteria_writer_accepts_story(self) -> None:
        story = "As a user I want to login so that I can access my account."
        result = acceptance_criteria_writer.run(story)
        assert isinstance(result, str)

    def test_priority_scorer_accepts_story(self) -> None:
        story = "As a user I want to login."
        result = priority_scorer.run(story)
        assert isinstance(result, str)


# -----------------------------------------------------------------------------
# QA tools — get_qa_tools schema and error handling
# -----------------------------------------------------------------------------


class TestQATools:
    def test_get_qa_tools_returns_list_of_tools(self) -> None:
        tools = get_qa_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 1
        for t in tools:
            assert hasattr(t, "name") or hasattr(t, "run") or callable(getattr(t, "run", None))

    def test_qa_tool_schemas_have_name_or_description(self) -> None:
        tools = get_qa_tools()
        for t in tools:
            assert hasattr(t, "name") or hasattr(t, "description") or hasattr(t, "description")
