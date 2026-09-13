"""Project artifact REST routes (R13)."""

from __future__ import annotations

from typing import Literal

from ai_team.ui.web.auth import require_token
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

router = APIRouter()
_AUTH = [Depends(require_token)]


@router.get("/api/projects/{project_id}/tree", dependencies=_AUTH)
async def project_tree(
    project_id: str,
    root: Literal["workspace", "bundle"] = Query(default="workspace"),
):
    """Nested file tree for a project workspace or results bundle."""
    from ai_team.ui.artifacts.service import build_tree

    try:
        nodes = build_tree(project_id, root)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"project_id": project_id, "root": root, "tree": [n.model_dump() for n in nodes]}


@router.get("/api/projects/{project_id}/file", dependencies=_AUTH)
async def project_file(
    project_id: str,
    path: str = Query(..., description="Relative file path"),
    root: Literal["workspace", "bundle"] = Query(default="workspace"),
):
    """Read a single artifact file (text) or return binary metadata."""
    from ai_team.ui.artifacts.service import read_artifact_file

    try:
        content = read_artifact_file(project_id, root, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if content.is_binary:
        raise HTTPException(
            status_code=415,
            detail={
                "message": "Binary file cannot be displayed as text",
                "size_bytes": content.size_bytes,
                "path": content.path,
            },
        )
    return content.model_dump()


@router.get("/api/projects/{project_id}/tests", dependencies=_AUTH)
async def project_tests(project_id: str):
    """Normalized test results for the Tests tab."""
    from ai_team.ui.artifacts.service import load_tests_panel

    try:
        panel = load_tests_panel(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return panel.model_dump()


@router.get("/api/projects/{project_id}/architecture", dependencies=_AUTH)
async def project_architecture(project_id: str):
    """Architecture document for the Architecture tab."""
    from ai_team.ui.artifacts.service import load_architecture_panel

    try:
        panel = load_architecture_panel(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return panel.model_dump()


@router.get("/api/projects/{project_id}/download.zip", dependencies=_AUTH)
async def project_download_zip(project_id: str):
    """Download workspace as ZIP."""
    from ai_team.ui.artifacts.service import workspace_zip_bytes

    try:
        data = workspace_zip_bytes(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{project_id}-workspace.zip"'},
    )
