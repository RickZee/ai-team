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
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

app = FastAPI(title="AI-Team Dashboard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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

    def create_run(self, run_id: str, backend: str, profile: str, description: str) -> dict:
        entry = {
            "run_id": run_id,
            "backend": backend,
            "profile": profile,
            "description": description,
            "status": "pending",
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "error": None,
        }
        self.runs[run_id] = entry
        return entry

    def finish_run(self, run_id: str, success: bool, error: str | None = None) -> None:
        if run_id in self.runs:
            self.runs[run_id]["status"] = "complete" if success else "error"
            self.runs[run_id]["finished_at"] = datetime.now().isoformat()
            self.runs[run_id]["error"] = error


state = RunState()

# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    backend: str = "langgraph"
    profile: str = "full"
    description: str
    complexity: str = "medium"


class EstimateRequest(BaseModel):
    complexity: str = "medium"


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


@app.get("/api/backends")
async def list_backends():
    """List available backends."""
    return {
        "backends": [
            {"name": "crewai", "label": "CrewAI", "streaming": False},
            {"name": "langgraph", "label": "LangGraph", "streaming": True},
        ]
    }


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
        return {"error": "Run not found"}, 404

    monitor = state.monitors.get(run_id)
    monitor_data = _serialize_monitor(monitor) if monitor else None
    return {**run, "monitor": monitor_data}


@app.post("/api/demo")
async def start_demo():
    """Start a demo run and return run_id (poll via /api/runs/{id} or connect WebSocket)."""
    run_id = str(uuid.uuid4())[:8]
    state.create_run(run_id, "demo", "full", "Demo: Flask REST API")
    # Fire and forget the demo in background
    asyncio.create_task(_run_demo_async(run_id))
    return {"run_id": run_id}


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

        run_id = str(uuid.uuid4())[:8]
        state.create_run(run_id, req.backend, req.profile, req.description)

        await websocket.send_json({"type": "run_started", "run_id": run_id})

        await _execute_run(websocket, run_id, req)

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

            if run["status"] in ("complete", "error"):
                await websocket.send_json({"type": "complete"})
                break

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Internal execution
# ---------------------------------------------------------------------------


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

        backend = get_backend(req.backend)

        if req.backend == "langgraph":
            from ai_team.backends.langgraph_backend.backend import LangGraphBackend

            if isinstance(backend, LangGraphBackend):
                loop = asyncio.get_event_loop()
                # Run blocking iter_stream_events in executor
                def _stream():
                    events = []
                    for ev in backend.iter_stream_events(req.description, profile, monitor=monitor):
                        events.append(ev)
                    return events

                events = await loop.run_in_executor(None, _stream)
                for ev in events:
                    await ws.send_json({
                        "type": "event",
                        "data": json.loads(json.dumps(ev, default=str)),
                    })
                    monitor_snap = _serialize_monitor(monitor)
                    await ws.send_json({"type": "monitor_update", "data": monitor_snap})
        else:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: backend.run(req.description, profile, env=None, monitor=monitor),
            )
            await ws.send_json({
                "type": "result",
                "data": json.loads(json.dumps(result.model_dump(), default=str)),
            })

        state.finish_run(run_id, success=True)
        await ws.send_json({
            "type": "complete",
            "data": _serialize_monitor(monitor),
        })

    except Exception as e:
        state.finish_run(run_id, success=False, error=str(e))
        await ws.send_json({"type": "error", "message": str(e)})


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
        fn()
        await asyncio.sleep(delay)

    try:
        await step(lambda: monitor.on_phase_change("intake"), 1.0)
        await step(lambda: monitor.on_log("system", "Received project: Create a Flask REST API", "info"))

        await step(lambda: monitor.on_phase_change("planning"))
        await step(lambda: monitor.on_agent_start("manager", "Coordinating planning phase", agents[0][1]), 1.0)
        await step(lambda: monitor.on_agent_start("product_owner", "Gathering requirements", agents[1][1]), 1.5)
        await step(lambda: monitor.on_guardrail("behavioral", "role_adherence", "pass"))
        await step(lambda: monitor.on_guardrail("quality", "requirements_completeness", "pass"))
        await step(lambda: monitor.on_agent_finish("product_owner", "Requirements gathering"))

        await step(lambda: monitor.on_agent_start("architect", "Designing system architecture", agents[2][1]), 2.0)
        await step(lambda: monitor.on_guardrail("behavioral", "scope_control", "pass"))
        await step(lambda: monitor.on_guardrail("quality", "architecture_completeness", "warn", "Missing deployment diagram"))
        await step(lambda: monitor.on_agent_finish("architect", "Architecture design"))
        await step(lambda: monitor.on_agent_finish("manager", "Planning coordination"))

        await step(lambda: monitor.on_phase_change("development"))
        await step(lambda: monitor.on_agent_start("backend_developer", "Implementing Flask routes", agents[3][1]), 2.0)
        await step(lambda: monitor.on_guardrail("security", "code_safety", "pass"))
        await step(lambda: monitor.on_guardrail("security", "secret_detection", "pass"))
        await step(lambda: monitor.on_file_generated("app.py"))
        await step(lambda: monitor.on_file_generated("requirements.txt"))
        await step(lambda: monitor.on_file_generated("config.py"))
        await step(lambda: monitor.on_agent_finish("backend_developer", "Flask API implementation"))

        await step(lambda: monitor.on_agent_start("devops", "Creating Dockerfile and CI config", agents[5][1]), 1.5)
        await step(lambda: monitor.on_file_generated("Dockerfile"))
        await step(lambda: monitor.on_file_generated(".github/workflows/ci.yml"))
        await step(lambda: monitor.on_agent_finish("devops", "DevOps setup"))

        await step(lambda: monitor.on_phase_change("testing"))
        await step(lambda: monitor.on_agent_start("qa_engineer", "Generating test cases", agents[4][1]), 1.5)
        await step(lambda: monitor.on_file_generated("test_app.py"))
        await step(lambda: monitor.on_guardrail("quality", "test_coverage", "pass"))
        await step(lambda: monitor.on_test_result(passed=8, failed=1))
        await step(lambda: monitor.on_retry("qa_engineer", "1 test failed: test_create_item_validation"))
        await step(lambda: monitor.on_agent_start("backend_developer", "Fixing validation", agents[3][1]), 1.5)
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

    except Exception as e:
        state.finish_run(run_id, success=False, error=str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_server(port: int = 8421, host: str = "0.0.0.0") -> None:
    """Run the FastAPI server."""
    # Serve React build if it exists
    frontend_dist = Path(__file__).parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

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
