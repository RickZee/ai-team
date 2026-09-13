"""Run REST routes (R13)."""

from __future__ import annotations

import asyncio
import contextlib
import os

import structlog
from ai_team.ui.web.auth import require_token
from ai_team.ui.web.server import (
    _TERMINAL_STATUSES,
    ResumeRequest,
    _capture_quality_gate_snapshot,
    _load_monitor_snapshot_from_bundle,
    _run_artifact_metrics,
    _serialize_monitor,
    state,
)
from fastapi import APIRouter, Depends, HTTPException, Query

logger = structlog.get_logger(__name__)

router = APIRouter()
_AUTH = [Depends(require_token)]


@router.get("/api/runs", dependencies=_AUTH)
async def list_runs():
    """List all runs."""
    return {"runs": list(state.runs.values())}


@router.get("/api/runs/history", dependencies=_AUTH)
async def run_history(limit: int = Query(200, ge=1, le=1000)):
    """Persisted run history (SQLite, data/memory.db) — survives server restarts.

    Unlike GET /api/runs (in-memory, wiped on restart), this reflects every run
    the server has ever started, including runs from a process that later died
    or was restarted mid-run. Registered before /api/runs/{run_id} so "history"
    isn't swallowed as a run_id path param.
    """
    if state.store is None:
        return {"runs": [], "persisted": False}
    return {"runs": state.store.list_runs(limit=limit), "persisted": True}


@router.get("/api/runs/{run_id}/receipt", dependencies=_AUTH)
async def get_run_receipt(run_id: str):
    """Return the on-disk change receipt. Source of truth; not the live event stream."""
    from ai_team.harness.receipt import load_receipt
    from ai_team.ui.artifacts.service import resolve_project_paths

    _ws, bundle = resolve_project_paths(run_id)
    receipt = load_receipt(bundle)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt.model_dump(mode="json")


@router.get("/api/runs/{run_id}", dependencies=_AUTH)
async def get_run(run_id: str):
    """Get run details including monitor state, spend, and artifact metrics."""
    run = state.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    from ai_team.core.spend_guard import current_spend

    monitor = state.monitors.get(run_id)
    monitor_data = _serialize_monitor(monitor, run_id) if monitor else None
    if monitor_data is None:
        monitor_data = _load_monitor_snapshot_from_bundle(run_id)
    return {
        **run,
        "project_id": run.get("project_id") or run_id,
        "monitor": monitor_data,
        # Subprocess-isolated backends (CrewAI) report spend via their result
        # payload (stashed on the run record); in-process backends are readable
        # from the run_id-keyed spend registry.
        "spend": run.get("spend") or current_spend(run_id=run_id),
        "metrics": _run_artifact_metrics(run_id),
    }


@router.get("/api/registry/runs", dependencies=_AUTH)
async def registry_runs():
    """List runs from disk registry merged with in-memory web sessions."""
    from ai_team.ui.artifacts.service import load_registry

    rows = load_registry(list(state.runs.values()))
    return {"runs": [r.model_dump() for r in rows]}


@router.post("/api/runs/{run_id}/resume", dependencies=_AUTH)
async def resume_run(run_id: str, req: ResumeRequest):
    """Resume a LangGraph run blocked on human review (HITL)."""
    run = state.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run["status"] != "awaiting_human":
        raise HTTPException(status_code=400, detail="Run is not awaiting human input")
    if run["backend"] != "langgraph":
        raise HTTPException(status_code=400, detail="Resume only supported for langgraph backend")

    feedback = (req.feedback or "").strip()
    if not feedback:
        raise HTTPException(status_code=400, detail="Feedback is required")

    from ai_team.backends.langgraph_backend.backend import LangGraphBackend
    from ai_team.backends.registry import get_backend
    from ai_team.core.team_profile import load_team_profile

    backend = get_backend("langgraph")
    if not isinstance(backend, LangGraphBackend):
        raise HTTPException(status_code=500, detail="LangGraph backend unavailable")

    profile = load_team_profile(run["profile"])
    thread_id = str(run.get("thread_id") or run_id)
    monitor = state.monitors.get(run_id)
    run["status"] = "running"

    loop = asyncio.get_event_loop()

    def _resume() -> None:
        # Match the graph_mode the original run used (see _stream_langgraph_events_to_ws).
        backend.resume(
            thread_id,
            feedback,
            profile,
            graph_mode=os.environ.get("AI_TEAM_LANGGRAPH_GRAPH_MODE", "full"),
        )

    try:
        await loop.run_in_executor(None, _resume)
        # A resume that reaches terminal did so on the operator's say-so, not
        # by passing the quality gate — record that distinctly so the registry
        # and comparison tables don't over-report green (state.json may still
        # say passed: False for this run).
        run["approved_via_hitl"] = True
        run["quality_gate_at_approval"] = _capture_quality_gate_snapshot(run_id)
        state.finish_run(run_id, success=True)
        return {
            "run_id": run_id,
            "status": "complete_approved",
            "approved_via_hitl": True,
            "quality_gate_at_approval": run.get("quality_gate_at_approval"),
            "monitor": _serialize_monitor(monitor, run_id) if monitor else None,
        }
    except Exception as e:
        state.finish_run(run_id, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/demo", dependencies=_AUTH)
async def start_demo():
    """Start a demo run and return run_id (poll via /api/runs/{id} or connect WebSocket)."""
    from ai_team.core.run_naming import resolve_run_id
    from ai_team.ui.web.server import _run_demo_async

    run_id = resolve_run_id(
        description="Demo: Flask REST API",
        team_profile="full",
        run_label="demo",
    )
    state.create_run(run_id, "demo", "full", "Demo: Flask REST API", is_sample=True)
    task = asyncio.create_task(_run_demo_async(run_id))
    state.tasks[run_id] = task
    return {"run_id": run_id}


@router.post("/api/runs/{run_id}/cancel", dependencies=_AUTH)
async def cancel_run(run_id: str):
    """Cancel a running run (cooperative cancel)."""
    run = state.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    terminal = _TERMINAL_STATUSES
    if run["status"] in terminal:
        raise HTTPException(status_code=400, detail=f"Run is already terminal ({run['status']})")
    state.cancel_run(run_id)
    return {"run_id": run_id, "status": "cancelling"}


@router.delete("/api/runs/{run_id}", dependencies=_AUTH)
async def delete_run_endpoint(run_id: str):
    """Delete a terminal run from disk and in-memory state."""
    from ai_team.core.results.cleanup import delete_run as delete_run_disk

    run = state.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    terminal = _TERMINAL_STATUSES
    if run["status"] not in terminal:
        raise HTTPException(
            status_code=400,
            detail=f"Run is not terminal ({run['status']}); cancel or wait before deleting",
        )
    disk_result = delete_run_disk(run_id)
    with contextlib.suppress(KeyError):
        state.remove_run(run_id)
    logger.info("run_deleted", run_id=run_id, existed_on_disk=disk_result.existed)
    return {
        "run_id": run_id,
        "deleted": True,
        "disk": disk_result.model_dump(),
    }
