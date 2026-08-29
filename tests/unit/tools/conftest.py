"""Shared fixtures for tool unit tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Temporary git repo with an initial commit on ``feature/test`` (main is protected for ``git_commit``)."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    subprocess.run(
        ["git", "init"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        env=env,
    )
    (repo_dir / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "commit", "-m", "chore: init"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "checkout", "-b", "feature/test"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        env=env,
    )
    return repo_dir


@pytest.fixture(autouse=True)
def _file_tool_bus_policy(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Existing file-tool tests expect live I/O. Opt into draft with ``bus_draft``."""
    if request.node.get_closest_marker("bus_draft"):
        return
    monkeypatch.setenv("AI_TEAM_DRAFT_WRITES", "0")
    monkeypatch.setenv("AI_TEAM_ALLOW_IRREVERSIBLE", "1")
