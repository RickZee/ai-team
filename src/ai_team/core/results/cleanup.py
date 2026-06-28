"""
Run cleanup: delete per-run workspace, output bundle, and registry entries.

Provides a shared, backend-agnostic API for removing a run as a single unit.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import structlog
from ai_team.config.settings import get_settings
from ai_team.core.results.writer import RUNS_SUBDIR, rebuild_registry
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class RunDeletionResult(BaseModel):
    """Outcome of deleting a single run's on-disk artifacts."""

    run_id: str = Field(description="Run identifier that was targeted for deletion")
    workspace_deleted: bool = Field(
        description="True when the workspace directory existed and was removed"
    )
    bundle_deleted: bool = Field(
        description="True when the output bundle directory existed and was removed"
    )
    existed: bool = Field(
        description="True when at least one of workspace or bundle existed before deletion"
    )


def validate_run_id(run_id: str) -> str:
    """Validate *run_id* and return it, or raise ``ValueError``."""
    if not run_id or ".." in run_id or "/" in run_id or "\\" in run_id:
        raise ValueError("Invalid run_id")
    return run_id


def _assert_child_path(root: Path, target: Path) -> Path:
    """Return resolved *target* if it is strictly inside *root*."""
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    if target_resolved == root_resolved:
        raise ValueError(f"Refusing to delete root directory: {root_resolved}")
    if root_resolved not in target_resolved.parents:
        raise ValueError(f"Path escapes root: {target_resolved}")
    return target_resolved


def _safe_rmtree(path: Path, root: Path) -> bool:
    """Remove *path* when it exists and is a strict child of *root*."""
    safe_path = _assert_child_path(root, path)
    if not safe_path.is_dir():
        return False
    shutil.rmtree(safe_path)
    return True


def delete_run(run_id: str) -> RunDeletionResult:
    """Delete workspace and output bundle for *run_id*, then rebuild the registry."""
    validated = validate_run_id(run_id)
    settings = get_settings()
    output_root = Path(settings.project.output_dir).resolve()
    workspace_root = Path(settings.project.workspace_dir).resolve()

    workspace_dir = workspace_root / validated
    bundle_dir = output_root / RUNS_SUBDIR / validated

    workspace_deleted = _safe_rmtree(workspace_dir, workspace_root)
    bundle_deleted = _safe_rmtree(bundle_dir, output_root)
    existed = workspace_deleted or bundle_deleted

    rebuild_registry(output_root)

    logger.info(
        "run_deleted",
        run_id=validated,
        workspace_deleted=workspace_deleted,
        bundle_deleted=bundle_deleted,
        existed=existed,
    )
    return RunDeletionResult(
        run_id=validated,
        workspace_deleted=workspace_deleted,
        bundle_deleted=bundle_deleted,
        existed=existed,
    )


def delete_runs(run_ids: list[str]) -> list[RunDeletionResult]:
    """Delete multiple runs; returns one result per id in order."""
    return [delete_run(run_id) for run_id in run_ids]
