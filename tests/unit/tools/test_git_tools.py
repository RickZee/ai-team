"""Unit tests for ``ai_team.tools.git_tools`` (init, branch, add, commit, status, diff, log)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from ai_team.tools.git_tools import (
    CommitInfo,
    GitStatus,
    create_pr_description,
    generate_commit_message,
    git_add,
    git_branch,
    git_commit,
    git_diff,
    git_init,
    git_log,
    git_status,
)
from git import InvalidGitRepositoryError


class TestGitInit:
    def test_init_creates_repo(self, tmp_path: Path) -> None:
        d = tmp_path / "newrepo"
        d.mkdir()
        assert git_init(str(d)) is True
        assert (d / ".git").exists()

    def test_init_idempotent_on_existing_repo(self, tmp_path: Path) -> None:
        d = tmp_path / "newrepo"
        d.mkdir()
        git_init(str(d))
        assert git_init(str(d)) is True

    def test_init_raises_on_file_not_directory(self, tmp_path: Path) -> None:
        f = tmp_path / "notdir"
        f.write_text("x", encoding="utf-8")
        with pytest.raises(NotADirectoryError):
            git_init(str(f))

    def test_init_path_must_exist(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            git_init(str(tmp_path / "missing"))


class TestGitBranch:
    def test_creates_and_checkouts_feature_branch(self, git_repo: Path) -> None:
        assert git_branch(str(git_repo), "feature/other") is True
        st = git_status(str(git_repo))
        assert st.branch == "feature/other"

    def test_rejects_protected_branch_names(self, git_repo: Path) -> None:
        with pytest.raises(ValueError, match="protected"):
            git_branch(str(git_repo), "main")
        with pytest.raises(ValueError, match="protected"):
            git_branch(str(git_repo), "master")

    def test_rejects_invalid_branch_format(self, git_repo: Path) -> None:
        with pytest.raises(ValueError, match="type/name"):
            git_branch(str(git_repo), "bad-branch")
        with pytest.raises(ValueError, match="spaces"):
            git_branch(str(git_repo), " feature/x")

    @pytest.mark.parametrize(
        "name",
        [
            "feature/a",
            "fix/b-1",
            "chore/c",
            "docs/readme",
            "refactor/r",
            "test/t",
            "build/ci",
        ],
    )
    def test_accepts_valid_prefixes(self, git_repo: Path, name: str) -> None:
        git_branch(str(git_repo), name)
        assert git_status(str(git_repo)).branch == name


class TestGitCommit:
    def test_commits_staged_changes(self, git_repo: Path) -> None:
        (git_repo / "a.txt").write_text("a", encoding="utf-8")
        git_add(str(git_repo), ["a.txt"])
        sha = git_commit(str(git_repo), "feat(scope): add file")
        assert len(sha) == 7
        log = git_log(str(git_repo), n=3)
        assert any("feat(scope): add file" in c.message for c in log)

    def test_blocks_commit_on_main(self, tmp_path: Path) -> None:
        repo = tmp_path / "r"
        repo.mkdir()
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        }
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, env=env)
        (repo / "f.txt").write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True, capture_output=True, env=env)
        subprocess.run(
            ["git", "commit", "-m", "chore: init"],
            cwd=repo,
            check=True,
            capture_output=True,
            env=env,
        )
        (repo / "b.txt").write_text("y", encoding="utf-8")
        git_add(str(repo), ["b.txt"])
        with pytest.raises(ValueError, match="main/master"):
            git_commit(str(repo), "feat: x")

    def test_requires_conventional_format(self, git_repo: Path) -> None:
        (git_repo / "c.txt").write_text("c", encoding="utf-8")
        git_add(str(git_repo), ["c.txt"])
        with pytest.raises(ValueError, match="conventional"):
            git_commit(str(git_repo), "no colon message")


class TestGitAdd:
    def test_stages_files(self, git_repo: Path) -> None:
        (git_repo / "n.txt").write_text("n", encoding="utf-8")
        assert git_add(str(git_repo), ["n.txt"]) is True
        st = git_status(str(git_repo))
        assert "n.txt" in st.staged_files or st.has_staged

    def test_rejects_files_outside_repo(self, git_repo: Path, tmp_path: Path) -> None:
        outside = tmp_path / "outside.txt"
        outside.write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="not inside repository"):
            git_add(str(git_repo), [str(outside)])

    def test_rejects_nonexistent_files(self, git_repo: Path) -> None:
        with pytest.raises(FileNotFoundError):
            git_add(str(git_repo), ["does-not-exist.txt"])


class TestGitStatus:
    def test_reports_staged_unstaged_untracked(self, git_repo: Path) -> None:
        (git_repo / "tracked.txt").write_text("1", encoding="utf-8")
        git_add(str(git_repo), ["tracked.txt"])
        git_commit(str(git_repo), "feat: track")
        (git_repo / "tracked.txt").write_text("2", encoding="utf-8")
        (git_repo / "new.txt").write_text("u", encoding="utf-8")
        st = git_status(str(git_repo))
        assert isinstance(st, GitStatus)
        assert st.has_untracked or "new.txt" in st.untracked_files

    def test_clean_repo(self, git_repo: Path) -> None:
        st = git_status(str(git_repo))
        assert st.branch == "feature/test"


class TestGitDiff:
    def test_shows_staged_and_working_tree(self, git_repo: Path) -> None:
        (git_repo / "d.txt").write_text("d", encoding="utf-8")
        git_add(str(git_repo), ["d.txt"])
        out = git_diff(str(git_repo))
        assert "staged" in out.lower() or "d.txt" in out

    def test_no_changes(self, git_repo: Path) -> None:
        assert "no changes" in git_diff(str(git_repo)).lower()


class TestGitLog:
    def test_returns_commit_info_list(self, git_repo: Path) -> None:
        log = git_log(str(git_repo), n=5)
        assert log
        assert isinstance(log[0], CommitInfo)
        assert log[0].sha
        assert log[0].message

    def test_limits_results(self, git_repo: Path) -> None:
        for i in range(3):
            (git_repo / f"x{i}.txt").write_text(str(i), encoding="utf-8")
            git_add(str(git_repo), [f"x{i}.txt"])
            git_commit(str(git_repo), f"feat: commit {i}")
        short = git_log(str(git_repo), n=2)
        assert len(short) <= 2


class TestGitOpenRouterHelpers:
    def test_generate_commit_message_empty_diff_no_key(self) -> None:
        with patch("ai_team.tools.git_tools.complete_with_openrouter", return_value=""):
            msg = generate_commit_message("")
            assert "feat:" in msg or "chore:" in msg

    def test_create_pr_description_empty_no_key(self) -> None:
        with patch("ai_team.tools.git_tools.complete_with_openrouter", return_value=""):
            body = create_pr_description([], [])
            assert "Summary" in body or "OPENROUTER" in body


class TestGitInvalidPath:
    def test_operations_require_git_repo(self, tmp_path: Path) -> None:
        d = tmp_path / "nogit"
        d.mkdir()
        (d / "f.txt").write_text("x", encoding="utf-8")
        with pytest.raises(InvalidGitRepositoryError):
            git_status(str(d))
