"""Workspace path resolution for eval runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def resolve_workspace(backend_name: str, raw_result: dict[str, Any]) -> Path | None:
    """Find the actual workspace directory from the backend result.

    Args:
        backend_name: Backend identifier (unused for resolution heuristics today).
        raw_result: Backend result dict that may contain thread/project/workspace keys.

    Returns:
        Resolved workspace path, or None when none can be located.
    """
    del backend_name  # reserved for backend-specific heuristics
    from ai_team.config.settings import get_settings

    try:
        ws_base = Path(get_settings().project.workspace_dir).resolve()
    except Exception:
        ws_base = Path("./workspace").resolve()

    run_id = (
        raw_result.get("thread_id")
        or raw_result.get("project_id")
        or (raw_result.get("state") or {}).get("project_id")
    )
    if run_id:
        candidate = ws_base / str(run_id)
        if candidate.exists():
            return candidate

    ws = raw_result.get("workspace_dir") or raw_result.get("workspace")
    if ws:
        path = Path(ws)
        if path.exists():
            return path.resolve()

    # No newest-directory fallback (R17.4). Guessing a sibling run assembles
    # a trace from the wrong workspace rather than reporting an error.
    return None
