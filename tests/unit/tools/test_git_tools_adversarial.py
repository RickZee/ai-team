"""Adversarial and injection-style tests for ``git_tools`` (paths, branch names, messages)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from ai_team.tools.git_tools import git_add, git_branch, git_commit


class TestGitAdversarialPaths:
    def test_path_traversal_string_rejected(self, git_repo: Path) -> None:
        with pytest.raises((ValueError, FileNotFoundError)):
            git_add(str(git_repo), ["../../../etc/passwd"])


class TestGitAdversarialBranch:
    def test_branch_injection_characters_rejected(self, git_repo: Path) -> None:
        with pytest.raises(ValueError):
            git_branch(str(git_repo), "feature/foo;rm -rf /")
        with pytest.raises(ValueError):
            git_branch(str(git_repo), "feature/foo\nbar")


class TestGitAdversarialCommitMessage:
    def test_empty_commit_message_rejected(self, git_repo: Path) -> None:
        (git_repo / "z.txt").write_text("z", encoding="utf-8")
        git_add(str(git_repo), ["z.txt"])
        with pytest.raises(ValueError, match="empty"):
            git_commit(str(git_repo), "   ")

    def test_multiline_still_requires_colon_on_first_line(self, git_repo: Path) -> None:
        (git_repo / "m.txt").write_text("m", encoding="utf-8")
        git_add(str(git_repo), ["m.txt"])
        with pytest.raises(ValueError, match="conventional"):
            git_commit(str(git_repo), "bad first line\nfeat: ok")


class TestGitAdversarialMainCommit:
    def test_cannot_commit_on_master(self, tmp_path: Path) -> None:
        repo = tmp_path / "m"
        repo.mkdir()
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        }
        subprocess.run(["git", "init", "-b", "master"], cwd=repo, check=True, capture_output=True, env=env)
        (repo / "a.txt").write_text("a", encoding="utf-8")
        subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True, capture_output=True, env=env)
        subprocess.run(
            ["git", "commit", "-m", "chore: init"],
            cwd=repo,
            check=True,
            capture_output=True,
            env=env,
        )
        (repo / "b.txt").write_text("b", encoding="utf-8")
        git_add(str(repo), ["b.txt"])
        with pytest.raises(ValueError, match="main/master"):
            git_commit(str(repo), "feat: x")
