"""Shared per-run workspace directories (eval + Claude backend)."""

from __future__ import annotations

from pathlib import Path

from ai_team.core.workspace_layout import ensure_workspace_layout


def test_ensure_workspace_layout_creates_dirs_and_brief(tmp_path: Path) -> None:
    ensure_workspace_layout(tmp_path, "Build a todo API")
    assert (tmp_path / "docs" / "contracts" / ".gitkeep").is_file()
    assert (tmp_path / "src").is_dir()
    assert (tmp_path / "tests").is_dir()
    assert (tmp_path / "logs").is_dir()
    brief = (tmp_path / "docs" / "project_brief.md").read_text(encoding="utf-8")
    assert "Build a todo API" in brief


def test_ensure_workspace_layout_does_not_overwrite_brief(tmp_path: Path) -> None:
    brief = tmp_path / "docs" / "project_brief.md"
    brief.parent.mkdir(parents=True)
    brief.write_text("keep-me", encoding="utf-8")
    ensure_workspace_layout(tmp_path, "new description")
    assert brief.read_text(encoding="utf-8") == "keep-me"
