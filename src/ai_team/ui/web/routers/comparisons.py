"""Compare-tab REST routes (R13)."""

from __future__ import annotations

from ai_team.ui.web.auth import require_token
from ai_team.ui.web.server import state
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter()
_AUTH = [Depends(require_token)]


@router.get("/api/comparisons", dependencies=_AUTH)
async def list_comparisons(limit: int = Query(50, ge=1, le=200)):
    """Recent Compare-tab sessions (grouped by comparison_id)."""
    if state.store is None:
        return {"comparisons": [], "persisted": False}
    return {"comparisons": state.store.list_comparisons(limit=limit), "persisted": True}


@router.get("/api/comparisons/{comparison_id}", dependencies=_AUTH)
async def get_comparison(comparison_id: str):
    """The 1-3 backend runs that belong to one Compare-tab session."""
    if state.store is None:
        raise HTTPException(status_code=503, detail="Run persistence unavailable")
    runs = state.store.get_comparison(comparison_id)
    if not runs:
        raise HTTPException(status_code=404, detail="Comparison not found")
    return {"comparison_id": comparison_id, "runs": runs}
