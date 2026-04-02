"""Adversarial tests for ``file_tools`` path validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ai_team.tools.file_tools import read_file, write_file


@pytest.fixture
def tmp_workspace(tmp_path: Path):
    """Temporary workspace with patched settings (same pattern as ``test_tools``)."""
    workspace = tmp_path / "workspace"
    output = tmp_path / "output"
    workspace.mkdir()
    output.mkdir()
    mock_settings = MagicMock()
    mock_settings.project.workspace_dir = str(workspace)
    mock_settings.project.output_dir = str(output)
    mock_settings.guardrails.max_file_size_kb = 500
    mock_settings.guardrails.dangerous_patterns = ["eval("]
    mock_settings.guardrails.pii_patterns = []
    with patch("ai_team.tools.file_tools.get_settings", return_value=mock_settings):
        yield workspace


class TestFileToolsAdversarialTraversal:
    def test_dotdot_in_path_rejected(self, tmp_workspace: Path) -> None:
        with pytest.raises(ValueError, match="traversal"):
            read_file("foo/../secret")

    def test_absolute_outside_workspace_rejected(self, tmp_workspace: Path) -> None:
        with pytest.raises(ValueError, match="allowed"):
            read_file("/etc/passwd")


class TestFileToolsPytestGuard:
    def test_write_rejects_root_level_test_py(self, tmp_workspace: Path) -> None:
        with pytest.raises(ValueError, match="pytest"):
            write_file("test_collect_me.py", "# not a real test")
