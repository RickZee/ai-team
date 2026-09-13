"""Health and catalog REST routes (R13)."""

from __future__ import annotations

import os
from datetime import datetime

from ai_team.ui.web.auth import require_token
from ai_team.ui.web.server import EstimateRequest
from fastapi import APIRouter, Depends

router = APIRouter()
_AUTH = [Depends(require_token)]

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


@router.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@router.get("/api/profiles", dependencies=_AUTH)
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


@router.get("/api/backends", dependencies=_AUTH)
async def list_backends():
    """List available backends with API key configuration hints."""
    backends = []
    for entry in _BACKEND_CATALOG:
        env_key = entry["required_key"]
        configured = bool(os.environ.get(env_key, "").strip())
        backends.append({**entry, "configured": configured})
    return {"backends": backends}


@router.post("/api/estimate", dependencies=_AUTH)
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
