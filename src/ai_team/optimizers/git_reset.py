"""
git_reset_hard — the one git primitive missing from git_tools.py.

Kept separate to avoid touching the security-reviewed git_tools module.
Uses an argument list with shell=False per CLAUDE.md security rules.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def git_reset_hard(workspace: Path, ref: str = "HEAD") -> bool:
    """
    Reset the working tree and index to *ref*.

    Returns True on success. Falls back gracefully — the caller should
    also call restore_workspace_subtrees() as a belt-and-suspenders measure.
    """
    result = subprocess.run(
        ["git", "reset", "--hard", ref],
        cwd=workspace,
        capture_output=True,
        text=True,
        shell=False,
    )
    if result.returncode != 0:
        logger.warning(
            "git_reset_hard_failed",
            ref=ref,
            stderr=result.stderr.strip(),
        )
        return False
    logger.info("git_reset_hard_ok", ref=ref)
    return True


def git_stash(workspace: Path) -> bool:
    """Stash uncommitted changes. Returns True on success."""
    result = subprocess.run(
        ["git", "stash"],
        cwd=workspace,
        capture_output=True,
        text=True,
        shell=False,
    )
    return result.returncode == 0


def git_stash_pop(workspace: Path) -> bool:
    """Pop the most recent stash. Returns True on success."""
    result = subprocess.run(
        ["git", "stash", "pop"],
        cwd=workspace,
        capture_output=True,
        text=True,
        shell=False,
    )
    return result.returncode == 0
