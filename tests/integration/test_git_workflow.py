"""Integration test: git tool workflow on a real temp repository."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from ai_team.tools.git_tools import git_add, git_branch, git_commit, git_init, git_log, git_status


@pytest.fixture
def integrated_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "integrated"
    repo.mkdir()
    git_init(str(repo))
    (repo / "src" / "app").mkdir(parents=True)
    (repo / "src" / "app" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "."],
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        },
    )
    subprocess.run(
        ["git", "commit", "-m", "chore: scaffold"],
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        },
    )
    subprocess.run(
        ["git", "checkout", "-b", "feature/workflow"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=os.environ,
    )
    return repo


def test_git_workflow_add_commit_status_log(integrated_repo: Path) -> None:
    (integrated_repo / "README.md").write_text("# Project\n", encoding="utf-8")
    git_add(str(integrated_repo), ["README.md"])
    sha = git_commit(str(integrated_repo), "docs: add readme")
    assert len(sha) == 7
    st = git_status(str(integrated_repo))
    assert st.branch == "feature/workflow"
    log = git_log(str(integrated_repo), n=5)
    assert any("docs: add readme" in e.message for e in log)


def test_git_branch_from_feature(integrated_repo: Path) -> None:
    git_branch(str(integrated_repo), "fix/small")
    assert git_status(str(integrated_repo)).branch == "fix/small"
