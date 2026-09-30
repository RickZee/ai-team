"""Strands on AgentCore. The pipeline is not built yet.

See ``.kiro/specs/aws-strands-agentcore``.
"""

from __future__ import annotations

from typing import Any

from ai_team.backends.common.thin_slice import scripted_result_or_none
from ai_team.core.backend import ThreadedBackend
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile

_SPEC = ".kiro/specs/aws-strands-agentcore"


class StrandsBackend(ThreadedBackend):
    """Placeholder. ``run`` raises until the AWS spec lands."""

    name: str = "strands"

    def run(
        self,
        description: str,
        profile: TeamProfile,
        env: str | None = None,
        **kwargs: Any,
    ) -> ProjectResult:
        scripted = scripted_result_or_none(self.name, description, profile, kwargs)
        if scripted is not None:
            return scripted
        _ = env
        target = kwargs.get("target") or "local"
        raise NotImplementedError(
            f"strands is not implemented yet: see {_SPEC}. "
            f"Supported targets: local, container, cloud. Requested target: {target}."
        )
