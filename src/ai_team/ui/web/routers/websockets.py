"""WebSocket routes (R13)."""

from __future__ import annotations

import asyncio
import contextlib

import structlog
from ai_team.ui.web.auth import accept_websocket
from ai_team.ui.web.server import (
    _TERMINAL_STATUSES,
    RunRequest,
    _serialize_monitor,
    _spawn_detached_run,
    state,
)
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/run")
async def ws_run(websocket: WebSocket):
    """
    WebSocket endpoint for running a backend with real-time streaming.

    Client sends JSON: {backend, profile, description, complexity}
    Server streams JSON events: {type, data} until {type: "complete"}
    """
    if not await accept_websocket(websocket):
        return
    try:
        msg = await websocket.receive_json()
        req = RunRequest(**msg)

        from ai_team.core.run_naming import resolve_run_id

        run_id = resolve_run_id(
            description=req.description,
            team_profile=req.profile,
        )
        state.create_run(
            run_id,
            req.backend,
            req.profile,
            req.description,
            estimate_usd=req.estimate_usd,
            complexity=req.complexity,
            comparison_id=req.comparison_id,
        )
        state.runs[run_id]["thread_id"] = run_id
        state.runs[run_id]["project_id"] = run_id

        await websocket.send_json({"type": "run_started", "run_id": run_id, "project_id": run_id})

        # The run executes in a detached task tracked by run_id so it survives
        # this socket. If the client navigates away (Run tab -> Dashboard) the
        # /ws/run socket closes, but the run keeps going and is observed via
        # /ws/monitor/{run_id}. We only cancel on an explicit cancel request
        # (state.cancel_run), never on client disconnect.
        task = _spawn_detached_run(websocket, run_id, req)
        state.tasks[run_id] = task
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            if (
                state.is_cancel_requested(run_id)
                and state.runs.get(run_id, {}).get("status") != "cancelled"
            ):
                monitor = state.monitors.get(run_id)
                state.finish_cancelled(run_id)
                with contextlib.suppress(Exception):
                    await websocket.send_json(
                        {
                            "type": "complete",
                            "run_status": "cancelled",
                            "data": _serialize_monitor(monitor),
                            "project_id": run_id,
                        }
                    )
            # Client disconnect (not an explicit cancel): the detached run task
            # keeps running; do not propagate cancellation to it.

    except WebSocketDisconnect:
        logger.info("ws_client_disconnected")
    except Exception as e:
        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "error", "message": str(e)})


@router.websocket("/ws/monitor/{run_id}")
async def ws_monitor(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for monitoring an active run.

    Pushes monitor state snapshots every 500ms while the run is active.
    """
    if not await accept_websocket(websocket):
        return
    try:
        while True:
            monitor = state.monitors.get(run_id)
            run = state.runs.get(run_id)
            if not run:
                await websocket.send_json({"type": "error", "message": "Run not found"})
                break

            data = _serialize_monitor(monitor, run_id) if monitor else {}
            data["run_status"] = run["status"]
            await websocket.send_json({"type": "monitor_update", "data": data})

            if run["status"] == "awaiting_human":
                payload = run.get("hitl_payload") or {}
                await websocket.send_json(
                    {
                        "type": "hitl_required",
                        "data": {**payload, "monitor": data, "run_id": run_id},
                    }
                )
                break

            if run["status"] in _TERMINAL_STATUSES:
                final_type = "error" if run["status"] == "error" else "complete"
                await websocket.send_json(
                    {
                        "type": final_type,
                        "run_status": run["status"],
                        "data": data,
                        "message": run.get("error"),
                    }
                )
                break

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
