"""Team profile loader: which agents and phases are active for a use case."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml
from pydantic import BaseModel, Field, field_validator

logger = structlog.get_logger(__name__)

_CONFIG_FILENAME = "team_profiles.yaml"


class TeamProfile(BaseModel):
    """Resolved team profile: agents, phases, and optional overrides."""

    name: str = Field(..., description="Profile key, e.g. full or backend-api.")
    agents: list[str] = Field(
        ...,
        description="Agent role keys included in this profile (see agents.yaml roles).",
    )
    phases: list[str] = Field(
        ...,
        description="Lifecycle phases included (intake, planning, development, testing, deployment).",
    )
    model_overrides: dict[str, str] = Field(
        default_factory=dict,
        description="Optional per-role model id overrides.",
    )
    tool_overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional per-role tool configuration overrides.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra profile data (e.g. RAG/MCP sections when wired).",
    )

    @field_validator("agents", "phases")
    @classmethod
    def _non_empty_lists(cls, v: list[str]) -> list[str]:
        if not v:
            msg = "agents and phases must each contain at least one entry"
            raise ValueError(msg)
        return v


def _profiles_yaml_path() -> Path:
    base = Path(__file__).resolve().parent.parent / "config" / _CONFIG_FILENAME
    return base


def load_team_profiles() -> dict[str, TeamProfile]:
    """Load all team profiles from ``config/team_profiles.yaml``."""
    path = _profiles_yaml_path()
    if not path.exists():
        logger.error("team_profiles_missing", path=str(path))
        raise FileNotFoundError(f"Team profiles config not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    profiles_raw = data.get("profiles") or {}
    out: dict[str, TeamProfile] = {}
    for key, spec in profiles_raw.items():
        if not isinstance(spec, dict):
            continue
        agents = list(spec.get("agents") or [])
        phases = list(spec.get("phases") or [])
        out[key] = TeamProfile(
            name=key,
            agents=agents,
            phases=phases,
            model_overrides=dict(spec.get("model_overrides") or {}),
            tool_overrides=dict(spec.get("tool_overrides") or {}),
            metadata={
                k: v
                for k, v in spec.items()
                if k not in {"agents", "phases", "model_overrides", "tool_overrides"}
            },
        )
    if not out:
        msg = "No profiles defined in team_profiles.yaml"
        raise ValueError(msg)
    return out


def load_team_profile(name: str) -> TeamProfile:
    """Load a single profile by name (raises ``KeyError`` if missing)."""
    profiles = load_team_profiles()
    if name not in profiles:
        available = ", ".join(sorted(profiles))
        raise KeyError(f"Unknown team profile {name!r}. Available: {available}")
    return profiles[name]


def default_team_profile() -> TeamProfile:
    """Return the ``full`` profile, or the first defined profile if ``full`` is absent."""
    profiles = load_team_profiles()
    if "full" in profiles:
        return profiles["full"]
    first = sorted(profiles.keys())[0]
    return profiles[first]
