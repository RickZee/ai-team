"""Microsoft Agent Framework on Azure AI Foundry. The pipeline is not built yet.

See ``.kiro/specs/azure-agent-framework``.
"""

from __future__ import annotations

from typing import Any

from ai_team.backends.common.thin_slice import scripted_result_or_none
from ai_team.core.backend import ThreadedBackend
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile

_SPEC = ".kiro/specs/azure-agent-framework"


class AgentFrameworkBackend(ThreadedBackend):
    """Placeholder. ``run`` raises until the Azure spec lands."""

    name: str = "agent-framework"

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
            "agent-framework is not implemented yet: see "
            f"{_SPEC}. Supported targets: local, container, cloud. "
            f"Requested target: {target}."
        )
