"""Comprehensive tests for file_tools including adversarial path inputs."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_team.tools.file_tools import (
    create_directory,
    delete_file,
    list_directory,
    read_file,
    write_file,
)


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temporary workspace and output dir and patch settings."""
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


# -----------------------------------------------------------------------------
# read_file
# -----------------------------------------------------------------------------


class TestReadFile:
    def test_read_file_success(self, tmp_workspace):
        (tmp_workspace / "hello.txt").write_text("hello world")
        assert read_file("hello.txt") == "hello world"
        assert read_file(str(tmp_workspace / "hello.txt")) == "hello world"

    def test_read_file_path_traversal_rejected(self, tmp_workspace):
        (tmp_workspace / "secret.txt").write_text("secret")
        with pytest.raises(ValueError, match="Path traversal"):
            read_file("../workspace/secret.txt")
        with pytest.raises(ValueError, match="Path traversal"):
            read_file("sub/../../secret.txt")
        with pytest.raises(ValueError, match="Path traversal"):
            read_file("..\\workspace\\secret.txt")

    def test_read_file_absolute_outside_rejected(self, tmp_workspace):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("outside")
            outside = f.name
        try:
            with pytest.raises(ValueError, match="not under allowed"):
                read_file(outside)
        finally:
            Path(outside).unlink(missing_ok=True)

    def test_read_file_nonexistent(self, tmp_workspace):
        with pytest.raises(ValueError, match="does not exist"):
            read_file("nonexistent.txt")

    def test_read_file_directory_rejected(self, tmp_workspace):
        (tmp_workspace / "adir").mkdir()
        with pytest.raises(ValueError, match="Not a file"):
            read_file("adir")

    def test_read_file_size_limit(self, tmp_workspace):
        big = "x" * (600 * 1024)  # 600 KB
        (tmp_workspace / "big.txt").write_text(big)
        with patch("ai_team.tools.file_tools.get_settings") as m:
            m.return_value = MagicMock()
            m.return_value.project.workspace_dir = str(tmp_workspace)
            m.return_value.project.output_dir = str(tmp_workspace / "out")
            m.return_value.guardrails.max_file_size_kb = 500
            m.return_value.guardrails.dangerous_patterns = []
            m.return_value.guardrails.pii_patterns = []
            with pytest.raises(ValueError, match="exceeds limit"):
                read_file("big.txt")


# -----------------------------------------------------------------------------
# write_file
# -----------------------------------------------------------------------------


class TestWriteFile:
    def test_write_file_success(self, tmp_workspace):
        assert write_file("new.txt", "content") is True
        assert (tmp_workspace / "new.txt").read_text() == "content"

    def test_write_file_path_traversal_rejected(self, tmp_workspace):
        with pytest.raises(ValueError, match="Path traversal"):
            write_file("../output/escape.txt", "x")
        with pytest.raises(ValueError, match="Path traversal"):
            write_file("a/../../etc/passwd", "x")

    def test_write_file_dangerous_pattern_rejected(self, tmp_workspace):
        with pytest.raises(ValueError, match="dangerous pattern"):
            write_file("bad.py", "import os; eval('x')")
        with pytest.raises(ValueError, match="dangerous pattern"):
            write_file("bad.py", "os.system('rm -rf /')")
        with pytest.raises(ValueError, match="dangerous pattern"):
            write_file("bad.py", "subprocess.call(['ls'])")
        with pytest.raises(ValueError, match="dangerous pattern"):
            write_file("bad.py", "__import__('os')")

    def test_write_file_safe_content_allowed(self, tmp_workspace):
        write_file("safe.py", "print('hello')")
        assert (tmp_workspace / "safe.py").read_text() == "print('hello')"


# -----------------------------------------------------------------------------
# list_directory
# -----------------------------------------------------------------------------


class TestListDirectory:
    def test_list_directory_success(self, tmp_workspace):
        (tmp_workspace / "a.txt").write_text("")
        (tmp_workspace / "b").mkdir()
        names = list_directory(".")
        assert "a.txt" in names
        assert "b" in names

    def test_list_directory_path_traversal_rejected(self, tmp_workspace):
        with pytest.raises(ValueError, match="Path traversal"):
            list_directory("../output")
        with pytest.raises(ValueError, match="Path traversal"):
            list_directory("sub/../..")

    def test_list_directory_not_a_directory(self, tmp_workspace):
        (tmp_workspace / "file.txt").write_text("")
        with pytest.raises(ValueError, match="Not a directory"):
            list_directory("file.txt")


# -----------------------------------------------------------------------------
# create_directory
# -----------------------------------------------------------------------------


class TestCreateDirectory:
    def test_create_directory_success(self, tmp_workspace):
        assert create_directory("subdir") is True
        assert (tmp_workspace / "subdir").is_dir()
        assert create_directory("subdir") is True  # idempotent

    def test_create_directory_nested(self, tmp_workspace):
        create_directory("a/b/c")
        assert (tmp_workspace / "a" / "b" / "c").is_dir()

    def test_create_directory_path_traversal_rejected(self, tmp_workspace):
        with pytest.raises(ValueError, match="Path traversal"):
            create_directory("../output/escape")
        with pytest.raises(ValueError, match="Path traversal"):
            create_directory("x/../../y")

    def test_create_directory_over_file_rejected(self, tmp_workspace):
        (tmp_workspace / "file.txt").write_text("")
        with pytest.raises(ValueError, match="not a directory"):
            create_directory("file.txt")


# -----------------------------------------------------------------------------
# delete_file
# -----------------------------------------------------------------------------


class TestDeleteFile:
    def test_delete_file_success(self, tmp_workspace):
        (tmp_workspace / "to_delete.txt").write_text("x")
        assert delete_file("to_delete.txt", confirm=True) is True
        assert not (tmp_workspace / "to_delete.txt").exists()

    def test_delete_file_requires_confirm(self, tmp_workspace):
        (tmp_workspace / "f.txt").write_text("x")
        with pytest.raises(ValueError, match="confirm=True"):
            delete_file("f.txt", confirm=False)
        assert (tmp_workspace / "f.txt").exists()

    def test_delete_file_path_traversal_rejected(self, tmp_workspace):
        (tmp_workspace / "secret.txt").write_text("x")
        with pytest.raises(ValueError, match="Path traversal"):
            delete_file("../workspace/secret.txt", confirm=True)
        assert (tmp_workspace / "secret.txt").exists()

    def test_delete_file_directory_rejected(self, tmp_workspace):
        (tmp_workspace / "adir").mkdir()
        with pytest.raises(ValueError, match="Not a file"):
            delete_file("adir", confirm=True)


# -----------------------------------------------------------------------------
# Tool decorator availability
# -----------------------------------------------------------------------------


class TestFileToolDecorators:
    def test_get_file_tools_returns_list(self):
        from ai_team.tools.file_tools import get_file_tools

        tools = get_file_tools()
        # May be empty if crewai not installed
        assert isinstance(tools, list)
        if tools:
            assert len(tools) == 5
