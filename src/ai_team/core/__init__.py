"""Backend-agnostic core: protocols, team profiles, and unified results."""

from ai_team.core.backend import Backend
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import (
    TeamProfile,
    default_team_profile,
    load_team_profile,
    load_team_profiles,
)

__all__ = [
    "Backend",
    "ProjectResult",
    "TeamProfile",
    "default_team_profile",
    "load_team_profile",
    "load_team_profiles",
]
