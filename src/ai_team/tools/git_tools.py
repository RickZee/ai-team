"""
Git tools: local repository operations with validation and safety checks.

All operations work with local git only (no GitHub API). Uses structured logging
and Pydantic models for CommitInfo and GitStatus. Safety: no force push,
no commits on main/master, branch naming convention enforced.
"""

import re
from pathlib import Path
from typing import List

import structlog
from git import GitCommandError, InvalidGitRepositoryError, Repo
from git.repo.fun import is_git_dir
from pydantic import BaseModel, Field

from ai_team.config.llm_factory import complete_with_openrouter

logger = structlog.get_logger(__name__)

# Protected branches: committing directly is disallowed
PROTECTED_BRANCHES = frozenset({"main", "master"})

# Branch name must match: type/name (e.g. feature/foo, fix/bar, chore/baz)
BRANCH_NAME_PATTERN = re.compile(r"^(feature|fix|chore|docs|refactor|test|build)/[a-zA-Z0-9._-]+$")


# -----------------------------------------------------------------------------
# Pydantic models
# -----------------------------------------------------------------------------


class CommitInfo(BaseModel):
    """Single commit entry from git log."""

    sha: str = Field(..., description="Short commit hash")
    message: str = Field(..., description="Commit message (first line)")
    author: str = Field(..., description="Author name")
    date: str = Field(..., description="Commit date (ISO-style string)")


class GitStatus(BaseModel):
    """Current repository status."""

    branch: str = Field(..., description="Current branch name")
    is_detached: bool = Field(..., description="True if HEAD is detached")
    has_staged: bool = Field(..., description="True if there are staged changes")
    has_unstaged: bool = Field(..., description="True if there are unstaged changes")
    has_untracked: bool = Field(..., description="True if there are untracked files")
    staged_files: List[str] = Field(default_factory=list, description="List of staged file paths")
    unstaged_files: List[str] = Field(default_factory=list, description="List of unstaged file paths")
    untracked_files: List[str] = Field(default_factory=list, description="List of untracked file paths")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _resolve_path(path: str) -> Path:
    """Resolve path to absolute and ensure it exists."""
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Path does not exist: {p}")
    return p


def _get_repo_root(path: Path) -> Path:
    """Find git repo root containing path (or path itself if it is .git)."""
    current = path if path.is_dir() else path.parent
    while True:
        if (current / ".git").exists() and is_git_dir(current / ".git"):
            return current
        parent = current.parent
        if parent == current:
            raise InvalidGitRepositoryError(f"No git repository found above {path}")
        current = parent


def _ensure_repo(path: Path) -> Repo:
    """Validate path is inside a git repo and return Repo."""
    root = _get_repo_root(path)
    repo = Repo(root)
    if repo.bare:
        raise InvalidGitRepositoryError(f"Repository at {root} is bare")
    logger.debug("git_repo_resolved", repo_root=str(root), path=str(path))
    return repo


def _current_branch_name(repo: Repo) -> str:
    """Current branch name or 'HEAD' if detached."""
    try:
        return repo.active_branch.name
    except TypeError:
        return "HEAD"


def _is_protected_branch(repo: Repo) -> bool:
    """True if current branch is main or master."""
    return _current_branch_name(repo).lower() in PROTECTED_BRANCHES


def _validate_branch_name(branch_name: str) -> None:
    """Raise ValueError if branch name is protected or does not match convention."""
    if not branch_name or branch_name.strip() != branch_name:
        raise ValueError("Branch name must be non-empty and not have leading/trailing spaces")
    lower = branch_name.lower()
    if lower in PROTECTED_BRANCHES:
        raise ValueError(f"Branch name '{branch_name}' is protected; use a feature/fix branch")
    if not BRANCH_NAME_PATTERN.match(branch_name):
        raise ValueError(
            "Branch name must follow type/name (e.g. feature/my-feature, fix/bug-123)"
        )


def _validate_conventional_message(message: str) -> None:
    """Basic check for conventional commit format (type(scope): description)."""
    if not message or not message.strip():
        raise ValueError("Commit message cannot be empty")
    first_line = message.strip().split("\n")[0]
    # Allow: type: msg, type(scope): msg
    if ":" not in first_line:
        raise ValueError("Commit message should follow conventional format: type(scope): description")


# -----------------------------------------------------------------------------
# Git operations
# -----------------------------------------------------------------------------


def git_init(path: str) -> bool:
    """
    Initialize a new git repository at the given path.

    :param path: Directory path to initialize.
    :return: True if init succeeded.
    """
    p = _resolve_path(path)
    if not p.is_dir():
        raise NotADirectoryError(f"Not a directory: {p}")
    if (p / ".git").exists():
        logger.info("git_init_skipped", path=str(p), reason="already a git repo")
        return True
    try:
        Repo.init(p)
        logger.info("git_init", path=str(p))
        return True
    except Exception as e:
        logger.exception("git_init_failed", path=str(p), error=str(e))
        raise


def git_add(path: str, files: List[str]) -> bool:
    """
    Stage the given files in the repository containing path.

    :param path: Path inside the repo (file or directory).
    :param files: List of paths to add (relative to repo root or absolute).
    :return: True if add succeeded.
    """
    repo = _ensure_repo(_resolve_path(path))
    repo_root = Path(repo.working_dir)
    resolved = []
    for f in files:
        fp = Path(f)
        if not fp.is_absolute():
            fp = repo_root / f
        else:
            fp = fp.resolve()
        try:
            rel = fp.relative_to(repo_root)
        except ValueError:
            raise ValueError(f"File {f} is not inside repository {repo_root}")
        if not fp.exists():
            raise FileNotFoundError(f"Path does not exist: {fp}")
        resolved.append(str(rel))
    try:
        repo.index.add(resolved)
        repo.index.write()
        logger.info("git_add", path=str(repo.working_dir), files=resolved)
        return True
    except GitCommandError as e:
        logger.exception("git_add_failed", path=str(repo.working_dir), error=str(e))
        raise


def git_commit(path: str, message: str) -> str:
    """
    Create a commit with the given message. Uses conventional commit format.
    Fails if current branch is main or master.

    :param path: Path inside the repo.
    :param message: Conventional commit message (type(scope): description).
    :return: Commit SHA (short) of the new commit.
    """
    repo = _ensure_repo(_resolve_path(path))
    if _is_protected_branch(repo):
        logger.warning("git_commit_blocked", branch=_current_branch_name(repo), reason="protected_branch")
        raise ValueError(
            "Committing directly to main/master is not allowed. Create a feature branch first."
        )
    _validate_conventional_message(message)
    try:
        commit = repo.index.commit(message)
        sha = commit.hexsha[:7]
        logger.info("git_commit", path=str(repo.working_dir), sha=sha, message_first_line=message.split("\n")[0])
        return sha
    except GitCommandError as e:
        logger.exception("git_commit_failed", path=str(repo.working_dir), error=str(e))
        raise


def git_branch(path: str, branch_name: str) -> bool:
    """
    Create and checkout a new branch. Enforces branch naming (type/name).

    :param path: Path inside the repo.
    :param branch_name: New branch name (e.g. feature/my-feature).
    :return: True if branch was created and checked out.
    """
    repo = _ensure_repo(_resolve_path(path))
    _validate_branch_name(branch_name)
    try:
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()
        logger.info("git_branch", path=str(repo.working_dir), branch=branch_name)
        return True
    except GitCommandError as e:
        logger.exception("git_branch_failed", path=str(repo.working_dir), branch=branch_name, error=str(e))
        raise


def git_diff(path: str) -> str:
    """
    Return the current unstaged and staged diff as a string.

    :param path: Path inside the repo.
    :return: Diff output (combined working tree and index).
    """
    repo = _ensure_repo(_resolve_path(path))
    try:
        diff = repo.git.diff()
        staged = repo.git.diff("--cached")
        out = ""
        if staged:
            out += "--- staged ---\n" + staged
        if diff:
            out += "\n--- working tree ---\n" + diff
        if not out:
            out = "(no changes)"
        logger.debug("git_diff", path=str(repo.working_dir), has_staged=bool(staged), has_unstaged=bool(diff))
        return out.strip()
    except GitCommandError as e:
        logger.exception("git_diff_failed", path=str(repo.working_dir), error=str(e))
        raise


def git_log(path: str, n: int = 10) -> List[CommitInfo]:
    """
    Return the most recent n commits as a list of CommitInfo.

    :param path: Path inside the repo.
    :param n: Number of commits to return.
    :return: List of CommitInfo.
    """
    repo = _ensure_repo(_resolve_path(path))
    try:
        commits = list(repo.iter_commits(max_count=n))
        result = [
            CommitInfo(
                sha=c.hexsha[:7],
                message=c.message.split("\n")[0] if c.message else "",
                author=c.author.name,
                date=c.committed_datetime.isoformat() if c.committed_datetime else "",
            )
            for c in commits
        ]
        logger.debug("git_log", path=str(repo.working_dir), n=n, count=len(result))
        return result
    except GitCommandError as e:
        logger.exception("git_log_failed", path=str(repo.working_dir), error=str(e))
        raise


def git_status(path: str) -> GitStatus:
    """
    Return current repository status as GitStatus.

    :param path: Path inside the repo.
    :return: GitStatus model.
    """
    repo = _ensure_repo(_resolve_path(path))
    try:
        branch = _current_branch_name(repo)
        try:
            is_detached = repo.head.is_detached
        except Exception:
            is_detached = branch == "HEAD"
        staged = [item.a_path for item in repo.index.diff("HEAD")]
        unstaged = [item.a_path for item in repo.index.diff(None)]
        untracked = repo.untracked_files
        status = GitStatus(
            branch=branch,
            is_detached=is_detached,
            has_staged=len(staged) > 0,
            has_unstaged=len(unstaged) > 0,
            has_untracked=len(untracked) > 0,
            staged_files=staged,
            unstaged_files=unstaged,
            untracked_files=untracked,
        )
        logger.debug("git_status", path=str(repo.working_dir), branch=branch)
        return status
    except GitCommandError as e:
        logger.exception("git_status_failed", path=str(repo.working_dir), error=str(e))
        raise


def generate_commit_message(diff: str) -> str:
    """
    Generate a conventional commit message from a diff using OpenRouter.

    :param diff: Git diff text.
    :return: Suggested commit message (single line or multi-line conventional).
    """
    prompt = """Given the following git diff, suggest a single conventional commit message.
Use format: type(scope): short description
Types: feat, fix, docs, style, refactor, test, chore.
Keep the first line under 72 characters. You may add a blank line and body if needed.

Diff:
"""
    prompt += diff if diff else "(no diff)"
    text = complete_with_openrouter(prompt)
    if not text:
        return "feat: update (run with OPENROUTER_API_KEY for better message)"
    first = text.split("\n")[0].strip()
    if not first:
        return "chore: update"
    logger.info("generate_commit_message", suggestion=first)
    return first


def create_pr_description(commits: List[str], changes: List[str]) -> str:
    """
    Generate a PR description from a list of commit messages and change summary (OpenRouter).

    :param commits: List of commit message strings.
    :param changes: List of change descriptions or file paths.
    :return: Generated PR body text.
    """
    commits_text = "\n".join(f"- {c}" for c in commits) if commits else "- (no commits)"
    changes_text = "\n".join(f"- {ch}" for ch in changes) if changes else "- (no changes listed)"
    prompt = f"""Write a short pull request description (2-4 paragraphs) that includes:
1. A brief summary of what this PR does.
2. Key changes (based on commits and changes below).
3. Any notes for reviewers.

Commits:
{commits_text}

Changes:
{changes_text}

Output only the PR description, no preamble."""
    text = complete_with_openrouter(prompt)
    if not text:
        return "## Summary\n\n(Enable OPENROUTER_API_KEY for generated description.)"
    logger.info("create_pr_description", length=len(text))
    return text
