"""Filesystem snapshots of workspace subtrees (complement to SDK file checkpointing)."""

from __future__ import annotations

import shutil
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

_SNAPSHOT_SUBDIRS = ("docs", "src", "tests", "infrastructure")


def snapshot_workspace_subtrees(workspace: Path, tag: str) -> Path:
    """
    Copy key subtrees into ``workspace/.ai_team_snapshots/<tag>/``.

    Used before a run or phase so ``restore_workspace_subtrees`` can roll back
    when validation fails (Bash file changes are not tracked).
    """
    root = workspace / ".ai_team_snapshots" / tag
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    for name in _SNAPSHOT_SUBDIRS:
        src = workspace / name
        if not src.exists():
            continue
        dest = root / name
        shutil.copytree(src, dest, dirs_exist_ok=True)
    logger.info("claude_workspace_snapshot_created", tag=tag, path=str(root))
    return root


def restore_workspace_subtrees(workspace: Path, tag: str) -> bool:
    """Restore subtrees from ``.ai_team_snapshots/<tag>/``. Returns False if missing."""
    root = workspace / ".ai_team_snapshots" / tag
    if not root.is_dir():
        logger.warning("claude_workspace_snapshot_missing", tag=tag)
        return False
    for name in _SNAPSHOT_SUBDIRS:
        snap = root / name
        dest = workspace / name
        if snap.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(snap, dest, dirs_exist_ok=True)
    logger.info("claude_workspace_snapshot_restored", tag=tag)
    return True
