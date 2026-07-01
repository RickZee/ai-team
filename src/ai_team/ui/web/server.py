"""
FastAPI server for AI-Team web dashboard.

Exposes REST + WebSocket endpoints for running backends, streaming events,
cost estimation, and real-time monitor state.

Usage:
    ai-team-web                   # Launch server + open browser
    ai-team-web --port 8421       # Custom port
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

ComplexityOption = Literal["simple", "medium", "complex"]

# LangGraph's checkpointer defaults to an in-memory SQLite DB per compile() call
# when AI_TEAM_LANGGRAPH_SQLITE_PATH is unset. The web server compiles the graph
# more than once per run (the streaming dispatch, then a separate compile in
# _langgraph_hitl_status to read back state for HITL detection) — with two
# independent in-memory DBs, the status check can never see the streaming
# call's checkpoints, so a run that actually paused on human_review silently
# reports as "complete" instead of "awaiting_human". Default to a persistent
# file so every compile in this process shares the same checkpoint store;
# an explicit env var still overrides.
os.environ.setdefault(
    "AI_TEAM_LANGGRAPH_SQLITE_PATH",
    str(Path(__file__).resolve().parents[4] / "workspace" / ".langgraph_checkpoints.sqlite"),
)

app = FastAPI(title="AI-Team Dashboard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in os.environ.get(
            "AI_TEAM_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8421",
        ).split(",")
        if o.strip()
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# State — active runs tracked in memory
# ---------------------------------------------------------------------------


class RunState:
    """Tracks active and completed runs."""

    def __init__(self) -> None:
        self.runs: dict[str, dict[str, Any]] = {}
        self.monitors: dict[str, Any] = {}  # run_id -> TeamMonitor
        self.tasks: dict[str, asyncio.Task] = {}  # run_id -> background task
        self.cancel_flags: dict[str, bool] = {}  # run_id -> cancel requested

    def create_run(
        self,
        run_id: str,
        backend: str,
        profile: str,
        description: str,
        estimate_usd: float | None = None,
        complexity: str | None = None,
        is_sample: bool = False,
    ) -> dict:
        entry = {
            "run_id": run_id,
            "backend": backend,
            "profile": profile,
            "description": description,
            "status": "pending",
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "error": None,
            "thread_id": run_id,
            "project_id": run_id,
            "hitl_payload": None,
            "estimate_usd": estimate_usd,
            "complexity": complexity,
            "is_sample": is_sample,
        }
        self.runs[run_id] = entry
        self.cancel_flags[run_id] = False
        return entry

    def set_awaiting_human(self, run_id: str, payload: dict[str, Any]) -> None:
        if run_id in self.runs:
            self.runs[run_id]["status"] = "awaiting_human"
            self.runs[run_id]["hitl_payload"] = payload

    def finish_run(self, run_id: str, success: bool, error: str | None = None) -> None:
        if run_id in self.runs:
            self.runs[run_id]["status"] = "complete" if success else "error"
            self.runs[run_id]["finished_at"] = datetime.now().isoformat()
            self.runs[run_id]["error"] = error
            self.runs[run_id]["hitl_payload"] = None
        self.tasks.pop(run_id, None)

    def cancel_run(self, run_id: str) -> None:
        """Mark a run as cancelling and request cooperative cancel."""
        if run_id in self.runs:
            self.runs[run_id]["status"] = "cancelling"
            self.cancel_flags[run_id] = True
            task = self.tasks.get(run_id)
            if task and not task.done():
                task.cancel()

    def finish_cancelled(self, run_id: str) -> None:
        if run_id in self.runs:
            self.runs[run_id]["status"] = "cancelled"
            self.runs[run_id]["finished_at"] = datetime.now().isoformat()
            self.runs[run_id]["hitl_payload"] = None
        self.tasks.pop(run_id, None)

    def is_cancel_requested(self, run_id: str) -> bool:
        return self.cancel_flags.get(run_id, False)

    def remove_run(self, run_id: str) -> None:
        """Remove a terminal run from in-memory state.

        Raises:
            KeyError: If the run is not tracked.
            ValueError: If the run is not in a terminal status.
        """
        run = self.runs.get(run_id)
        if run is None:
            raise KeyError(f"Run not found: {run_id}")
        terminal = {"complete", "error", "cancelled"}
        if run["status"] not in terminal:
            raise ValueError(f"Run is not terminal ({run['status']})")
        self.runs.pop(run_id, None)
        self.monitors.pop(run_id, None)
        self.tasks.pop(run_id, None)
        self.cancel_flags.pop(run_id, None)


state = RunState()

# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    backend: str = "langgraph"
    profile: str = "full"
    description: str
    complexity: ComplexityOption = "medium"
    estimate_usd: float | None = None


class EstimateRequest(BaseModel):
    complexity: ComplexityOption = "medium"


class ResumeRequest(BaseModel):
    feedback: str


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/profiles")
async def list_profiles():
    """List available team profiles."""
    from ai_team.core.team_profile import load_team_profiles

    profiles = load_team_profiles()
    return {
        name: {
            "agents": p.agents,
            "phases": p.phases,
            "model_overrides": p.model_overrides,
        }
        for name, p in profiles.items()
    }


_BACKEND_CATALOG = [
    {
        "name": "crewai",
        "label": "CrewAI",
        "streaming": False,
        "required_key": "OPENROUTER_API_KEY",
    },
    {
        "name": "langgraph",
        "label": "LangGraph",
        "streaming": True,
        "required_key": "OPENROUTER_API_KEY",
    },
    {
        "name": "claude-agent-sdk",
        "label": "Claude Agent SDK",
        "streaming": True,
        "required_key": "ANTHROPIC_API_KEY",
    },
]


@app.get("/api/backends")
async def list_backends():
    """List available backends with API key configuration hints."""
    backends = []
    for entry in _BACKEND_CATALOG:
        env_key = entry["required_key"]
        configured = bool(os.environ.get(env_key, "").strip())
        backends.append({**entry, "configured": configured})
    return {"backends": backends}


@app.post("/api/estimate")
async def estimate_cost(req: EstimateRequest):
    """Return cost estimate for a run."""
    from ai_team.config.cost_estimator import estimate_run_cost
    from ai_team.config.models import OpenRouterSettings

    settings = OpenRouterSettings()
    rows, total, within_budget = estimate_run_cost(settings, req.complexity)
    return {
        "complexity": req.complexity,
        "rows": [
            {
                "role": r.role,
                "model_id": r.model_id,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": r.cost_usd,
            }
            for r in rows
        ],
        "total_usd": total,
        "within_budget": within_budget,
    }


@app.get("/api/runs")
async def list_runs():
    """List all runs."""
    return {"runs": list(state.runs.values())}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """Get run details including monitor state."""
    run = state.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    monitor = state.monitors.get(run_id)
    monitor_data = _serialize_monitor(monitor) if monitor else None
    return {**run, "project_id": run.get("project_id") or run_id, "monitor": monitor_data}


@app.get("/api/registry/runs")
async def registry_runs():
    """List runs from disk registry merged with in-memory web sessions."""
    from ai_team.ui.artifacts.service import load_registry

    rows = load_registry(list(state.runs.values()))
    return {"runs": [r.model_dump() for r in rows]}


@app.get("/api/projects/{project_id}/tree")
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


@app.get("/api/projects/{project_id}/file")
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


@app.get("/api/projects/{project_id}/tests")
async def project_tests(project_id: str):
    """Normalized test results for the Tests tab."""
    from ai_team.ui.artifacts.service import load_tests_panel

    try:
        panel = load_tests_panel(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return panel.model_dump()


@app.get("/api/projects/{project_id}/architecture")
async def project_architecture(project_id: str):
    """Architecture document for the Architecture tab."""
    from ai_team.ui.artifacts.service import load_architecture_panel

    try:
        panel = load_architecture_panel(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return panel.model_dump()


@app.get("/api/projects/{project_id}/download.zip")
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


@app.post("/api/runs/{run_id}/resume")
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
        state.finish_run(run_id, success=True)
        return {
            "run_id": run_id,
            "status": "complete",
            "monitor": _serialize_monitor(monitor) if monitor else None,
        }
    except Exception as e:
        state.finish_run(run_id, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/demo")
async def start_demo():
    """Start a demo run and return run_id (poll via /api/runs/{id} or connect WebSocket)."""
    from ai_team.core.run_naming import resolve_run_id

    run_id = resolve_run_id(
        description="Demo: Flask REST API",
        team_profile="full",
        run_label="demo",
    )
    state.create_run(run_id, "demo", "full", "Demo: Flask REST API", is_sample=True)
    task = asyncio.create_task(_run_demo_async(run_id))
    state.tasks[run_id] = task
    return {"run_id": run_id}


@app.post("/api/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    """Cancel a running run (cooperative cancel)."""
    run = state.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    terminal = {"complete", "error", "cancelled"}
    if run["status"] in terminal:
        raise HTTPException(status_code=400, detail=f"Run is already terminal ({run['status']})")
    state.cancel_run(run_id)
    return {"run_id": run_id, "status": "cancelling"}


@app.delete("/api/runs/{run_id}")
async def delete_run_endpoint(run_id: str):
    """Delete a terminal run from disk and in-memory state."""
    from ai_team.core.results.cleanup import delete_run as delete_run_disk

    run = state.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    terminal = {"complete", "error", "cancelled"}
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


# ---------------------------------------------------------------------------
# WebSocket — real-time streaming
# ---------------------------------------------------------------------------


@app.websocket("/ws/run")
async def ws_run(websocket: WebSocket):
    """
    WebSocket endpoint for running a backend with real-time streaming.

    Client sends JSON: {backend, profile, description, complexity}
    Server streams JSON events: {type, data} until {type: "complete"}
    """
    await websocket.accept()
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


@app.websocket("/ws/monitor/{run_id}")
async def ws_monitor(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for monitoring an active run.

    Pushes monitor state snapshots every 500ms while the run is active.
    """
    await websocket.accept()
    try:
        while True:
            monitor = state.monitors.get(run_id)
            run = state.runs.get(run_id)
            if not run:
                await websocket.send_json({"type": "error", "message": "Run not found"})
                break

            data = _serialize_monitor(monitor) if monitor else {}
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

            if run["status"] in ("complete", "error", "cancelled"):
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


# ---------------------------------------------------------------------------
# Internal execution
# ---------------------------------------------------------------------------


# Strong references to detached run tasks so they are not garbage-collected
# while running (asyncio only keeps weak references to tasks).
_DETACHED_RUNS: set[asyncio.Task] = set()


def _spawn_detached_run(ws: WebSocket, run_id: str, req: RunRequest) -> asyncio.Task:
    """Run ``_execute_run`` detached from the request's task scope.

    The task is created on the running loop and retried once if it is
    cancelled by request teardown (client disconnect) without an explicit
    cancel having been requested. This guarantees that closing the ``/ws/run``
    socket — e.g. navigating from the Run tab to the Dashboard — never aborts
    an in-flight backend run.
    """

    task = asyncio.ensure_future(_execute_run(ws, run_id, req))
    _DETACHED_RUNS.add(task)
    task.add_done_callback(_DETACHED_RUNS.discard)
    return task


async def _safe_send(ws: WebSocket, payload: dict[str, Any]) -> None:
    """Send to the run WebSocket, ignoring a disconnected client.

    The run executes in a detached task that must outlive the ``/ws/run``
    socket: a user navigating from the Run tab to the Dashboard closes that
    socket, but the backend run keeps going and is observed via
    ``/ws/monitor/{run_id}``. Swallowing send failures here prevents a closed
    client socket from aborting an in-flight run.
    """
    with contextlib.suppress(Exception):
        await ws.send_json(payload)


async def _send_cancelled(ws: WebSocket, run_id: str) -> None:
    """Mark run cancelled and notify the WebSocket client."""
    if state.runs.get(run_id, {}).get("status") == "cancelled":
        return
    monitor = state.monitors.get(run_id)
    state.finish_cancelled(run_id)
    await _safe_send(
        ws,
        {
            "type": "complete",
            "run_status": "cancelled",
            "data": _serialize_monitor(monitor),
            "project_id": run_id,
        },
    )


async def _stream_langgraph_events_to_ws(
    ws: WebSocket,
    run_id: str,
    backend: Any,
    description: str,
    profile: Any,
    monitor: Any,
    thread_id: str,
) -> tuple[bool, dict[str, Any] | None]:
    """Incrementally stream LangGraph events to the client via a thread-safe queue."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    def _producer() -> None:
        try:
            for ev in backend.iter_stream_events(
                description,
                profile,
                monitor=monitor,
                thread_id=thread_id,
                # Web runs are real runs, not unit-test scaffolding: match the
                # CLI's run_demo.py default (graph_mode="full") so the LangGraph
                # column on the Compare tab actually executes the subgraphs
                # instead of the placeholder no-LLM stub completing instantly
                # with 0 files. AI_TEAM_LANGGRAPH_GRAPH_MODE still overrides.
                graph_mode=os.environ.get("AI_TEAM_LANGGRAPH_GRAPH_MODE", "full"),
            ):
                if state.is_cancel_requested(run_id):
                    break
                loop.call_soon_threadsafe(queue.put_nowait, ev)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=_producer, daemon=True).start()

    while True:
        if state.is_cancel_requested(run_id):
            await _send_cancelled(ws, run_id)
            return False, None
        ev = await queue.get()
        if ev is None:
            break
        await _safe_send(
            ws,
            {
                "type": "event",
                "data": json.loads(json.dumps(ev, default=str)),
            },
        )
        await _safe_send(ws, {"type": "monitor_update", "data": _serialize_monitor(monitor)})

    return _langgraph_hitl_status(backend, thread_id)


async def _execute_run(ws: WebSocket, run_id: str, req: RunRequest) -> None:
    """Execute a backend run, streaming events over WebSocket."""
    from ai_team.backends.registry import get_backend
    from ai_team.core.team_profile import load_team_profile
    from ai_team.monitor import TeamMonitor

    try:
        profile = load_team_profile(req.profile)
        monitor = TeamMonitor(project_name=req.description[:50])
        monitor.metrics.start_time = datetime.now()
        state.monitors[run_id] = monitor
        state.runs[run_id]["status"] = "running"

        if state.is_cancel_requested(run_id):
            await _send_cancelled(ws, run_id)
            return

        backend = get_backend(req.backend)

        if req.backend == "langgraph":
            from ai_team.backends.langgraph_backend.backend import LangGraphBackend

            if isinstance(backend, LangGraphBackend):
                thread_id = run_id
                awaiting, hitl_payload = await _stream_langgraph_events_to_ws(
                    ws,
                    run_id,
                    backend,
                    req.description,
                    profile,
                    monitor,
                    thread_id,
                )
                if state.is_cancel_requested(run_id):
                    return
                if awaiting:
                    payload = {
                        **(hitl_payload or {}),
                        "thread_id": thread_id,
                        "monitor": _serialize_monitor(monitor),
                    }
                    state.set_awaiting_human(run_id, payload)
                    await _safe_send(ws, {"type": "hitl_required", "data": payload})
                    return
        elif req.backend in ("claude-agent-sdk", "claude-sdk"):
            from ai_team.backends.claude_agent_sdk_backend.backend import ClaudeAgentBackend

            if isinstance(backend, ClaudeAgentBackend):
                async for ev in backend.stream(
                    req.description,
                    profile,
                    env=None,
                    monitor=monitor,
                    thread_id=run_id,
                ):
                    if state.is_cancel_requested(run_id):
                        await _send_cancelled(ws, run_id)
                        return
                    await _safe_send(
                        ws,
                        {
                            "type": "event",
                            "data": json.loads(json.dumps(ev, default=str)),
                        },
                    )
                    monitor_snap = _serialize_monitor(monitor)
                    await _safe_send(ws, {"type": "monitor_update", "data": monitor_snap})
        else:
            if state.is_cancel_requested(run_id):
                await _send_cancelled(ws, run_id)
                return
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: backend.run(
                    req.description,
                    profile,
                    env=None,
                    monitor=monitor,
                    thread_id=run_id,
                ),
            )
            if state.is_cancel_requested(run_id):
                await _send_cancelled(ws, run_id)
                return
            await _safe_send(
                ws,
                {
                    "type": "result",
                    "data": json.loads(json.dumps(result.model_dump(), default=str)),
                },
            )

        if state.is_cancel_requested(run_id):
            await _send_cancelled(ws, run_id)
            return

        state.finish_run(run_id, success=True)
        await _safe_send(
            ws,
            {
                "type": "complete",
                "data": _serialize_monitor(monitor),
                "project_id": run_id,
            },
        )

    except asyncio.CancelledError:
        if state.is_cancel_requested(run_id):
            await _send_cancelled(ws, run_id)
        raise
    except Exception as e:
        state.finish_run(run_id, success=False, error=str(e))
        await _safe_send(ws, {"type": "error", "message": str(e)})


async def _run_demo_async(run_id: str) -> None:
    """Run the demo simulation asynchronously, updating monitor state."""
    from ai_team.monitor import TeamMonitor

    monitor = TeamMonitor(project_name="Demo: Flask REST API")
    monitor.metrics.start_time = datetime.now()
    state.monitors[run_id] = monitor
    state.runs[run_id]["status"] = "running"

    agents = [
        ("manager", "qwen3:14b"),
        ("product_owner", "qwen3:14b"),
        ("architect", "deepseek-r1:14b"),
        ("backend_developer", "qwen2.5-coder:14b"),
        ("qa_engineer", "qwen3:14b"),
        ("devops", "qwen2.5-coder:14b"),
    ]

    async def step(fn, delay: float = 0.5):
        if state.is_cancel_requested(run_id):
            raise asyncio.CancelledError()
        fn()
        await asyncio.sleep(delay)

    try:
        await step(lambda: monitor.on_phase_change("intake"), 1.0)
        await step(
            lambda: monitor.on_log("system", "Received project: Create a Flask REST API", "info")
        )

        await step(lambda: monitor.on_phase_change("planning"))
        await step(
            lambda: monitor.on_agent_start("manager", "Coordinating planning phase", agents[0][1]),
            1.0,
        )
        await step(
            lambda: monitor.on_agent_start("product_owner", "Gathering requirements", agents[1][1]),
            1.5,
        )
        await step(lambda: monitor.on_guardrail("behavioral", "role_adherence", "pass"))
        await step(lambda: monitor.on_guardrail("quality", "requirements_completeness", "pass"))
        await step(lambda: monitor.on_agent_finish("product_owner", "Requirements gathering"))

        await step(
            lambda: monitor.on_agent_start(
                "architect", "Designing system architecture", agents[2][1]
            ),
            2.0,
        )
        await step(lambda: monitor.on_guardrail("behavioral", "scope_control", "pass"))
        await step(
            lambda: monitor.on_guardrail(
                "quality", "architecture_completeness", "warn", "Missing deployment diagram"
            )
        )
        await step(lambda: monitor.on_agent_finish("architect", "Architecture design"))
        await step(lambda: monitor.on_agent_finish("manager", "Planning coordination"))

        await step(lambda: monitor.on_phase_change("development"))
        await step(
            lambda: monitor.on_agent_start(
                "backend_developer", "Implementing Flask routes", agents[3][1]
            ),
            2.0,
        )
        await step(lambda: monitor.on_guardrail("security", "code_safety", "pass"))
        await step(lambda: monitor.on_guardrail("security", "secret_detection", "pass"))
        await step(lambda: monitor.on_file_generated("app.py"))
        await step(lambda: monitor.on_file_generated("requirements.txt"))
        await step(lambda: monitor.on_file_generated("config.py"))
        await step(lambda: monitor.on_agent_finish("backend_developer", "Flask API implementation"))

        await step(
            lambda: monitor.on_agent_start(
                "devops", "Creating Dockerfile and CI config", agents[5][1]
            ),
            1.5,
        )
        await step(lambda: monitor.on_file_generated("Dockerfile"))
        await step(lambda: monitor.on_file_generated(".github/workflows/ci.yml"))
        await step(lambda: monitor.on_agent_finish("devops", "DevOps setup"))

        await step(lambda: monitor.on_phase_change("testing"))
        await step(
            lambda: monitor.on_agent_start("qa_engineer", "Generating test cases", agents[4][1]),
            1.5,
        )
        await step(lambda: monitor.on_file_generated("test_app.py"))
        await step(lambda: monitor.on_guardrail("quality", "test_coverage", "pass"))
        await step(lambda: monitor.on_test_result(passed=8, failed=1))
        await step(
            lambda: monitor.on_retry("qa_engineer", "1 test failed: test_create_item_validation")
        )
        await step(
            lambda: monitor.on_agent_start("backend_developer", "Fixing validation", agents[3][1]),
            1.5,
        )
        await step(lambda: monitor.on_agent_finish("backend_developer", "Bug fix"))
        await step(lambda: monitor.on_test_result(passed=9, failed=0))
        await step(lambda: monitor.on_agent_finish("qa_engineer", "Test suite"))

        await step(lambda: monitor.on_phase_change("deployment"))
        await step(lambda: monitor.on_agent_start("devops", "Packaging project", agents[5][1]), 1.5)
        await step(lambda: monitor.on_file_generated("docker-compose.yml"))
        await step(lambda: monitor.on_file_generated("README.md"))
        await step(lambda: monitor.on_agent_finish("devops", "Deployment packaging"))

        await step(lambda: monitor.on_phase_change("complete"), 2.0)
        state.finish_run(run_id, success=True)

    except asyncio.CancelledError:
        state.finish_cancelled(run_id)
    except Exception as e:
        state.finish_run(run_id, success=False, error=str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _langgraph_hitl_status(backend: Any, thread_id: str) -> tuple[bool, dict[str, Any] | None]:
    """Return whether a LangGraph thread is paused for human review."""
    try:
        from ai_team.backends.langgraph_backend.state_inspection import get_thread_state_snapshot

        g = backend._compile_for_run(backend._graph_mode({}), None)
        snap = get_thread_state_snapshot(g, thread_id)
        values = snap.values if isinstance(snap.values, dict) else {}
        phase = str(values.get("current_phase") or "")
        if phase == "awaiting_human":
            meta = values.get("metadata") if isinstance(values.get("metadata"), dict) else {}
            return True, {
                "phase": phase,
                "thread_id": thread_id,
                "metadata": meta,
                "next": list(snap.next) if snap.next else [],
            }
        if snap.tasks:
            for task in snap.tasks:
                interrupts = getattr(task, "interrupts", None)
                if interrupts:
                    return True, {
                        "thread_id": thread_id,
                        "interrupts": json.loads(json.dumps(interrupts, default=str)),
                        "next": list(snap.next) if snap.next else [],
                    }
    except Exception as e:
        logger.debug("langgraph_hitl_check_skipped", error=str(e))
    return False, None


def _serialize_monitor(monitor) -> dict[str, Any]:
    """Serialize TeamMonitor state to JSON-safe dict."""
    if not monitor:
        return {}
    return {
        "phase": monitor.current_phase.value,
        "elapsed": monitor.metrics.elapsed_str,
        "agents": {
            role: {
                "role": a.role,
                "status": a.status,
                "current_task": a.current_task,
                "tasks_completed": a.tasks_completed,
                "model": a.model,
            }
            for role, a in monitor.agents.items()
        },
        "metrics": {
            "tasks_completed": monitor.metrics.tasks_completed,
            "tasks_failed": monitor.metrics.tasks_failed,
            "retries": monitor.metrics.retries,
            "files_generated": monitor.metrics.files_generated,
            "guardrails_passed": monitor.metrics.guardrails_passed,
            "guardrails_failed": monitor.metrics.guardrails_failed,
            "guardrails_warned": monitor.metrics.guardrails_warned,
            "tests_passed": monitor.metrics.tests_passed,
            "tests_failed": monitor.metrics.tests_failed,
        },
        "log": [
            {
                "timestamp": e.timestamp.isoformat(),
                "agent": e.agent,
                "message": e.message,
                "level": e.level,
            }
            for e in monitor.log[-50:]
        ],
        "guardrail_events": [
            {
                "timestamp": e.timestamp.isoformat(),
                "category": e.category,
                "name": e.name,
                "status": e.status,
                "message": e.message,
            }
            for e in monitor.guardrail_events[-20:]
        ],
        "token_estimate": monitor.metrics.token_estimate,
        "cost_usd": monitor.metrics.claude_cost_usd,
        "session_id": monitor.metrics.claude_session_id or None,
    }


# ---------------------------------------------------------------------------
# Frontend (SPA) — client-side routes need index.html fallback
# ---------------------------------------------------------------------------

_FRONTEND_REGISTERED = False


def register_frontend(app: FastAPI, frontend_dist: Path | None = None) -> None:
    """Serve the Vite build and fall back to ``index.html`` for React Router paths."""
    global _FRONTEND_REGISTERED
    if _FRONTEND_REGISTERED:
        return
    dist = frontend_dist or (Path(__file__).parent / "frontend" / "dist")
    index = dist / "index.html"
    if not index.exists():
        return

    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(assets_dir)),
            name="frontend_assets",
        )

    @app.get("/{spa_path:path}", include_in_schema=False)
    async def spa_catchall(spa_path: str) -> FileResponse:
        if spa_path.startswith("api") or spa_path.startswith("ws"):
            raise HTTPException(status_code=404, detail="Not Found")
        target = dist / spa_path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(index)

    _FRONTEND_REGISTERED = True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_server(port: int = 8421, host: str = "0.0.0.0") -> None:
    """Run the FastAPI server."""
    register_frontend(app)
    uvicorn.run(app, host=host, port=port)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="AI-Team Web Dashboard")
    parser.add_argument("--port", type=int, default=8421)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    run_server(port=args.port, host=args.host)


if __name__ == "__main__":
    main()
