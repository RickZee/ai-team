"""Registry accepts the cloud backend names and rejects a bad target before spend."""

from __future__ import annotations

import pytest
from ai_team.backends.common.targets import UnsupportedTargetError
from ai_team.backends.registry import get_backend, list_backend_names
from ai_team.core.spend_guard import current_spend


def test_catalog_includes_cloud_backends() -> None:
    names = list_backend_names()
    assert "strands" in names
    assert "agent-framework" in names


def test_strands_cloud_names_the_spec_before_spend() -> None:
    before = current_spend().get("spent_usd")
    with pytest.raises(NotImplementedError, match="aws-strands-agentcore"):
        get_backend("strands", target="cloud")
    assert current_spend().get("spent_usd") == before


def test_agent_framework_names_the_spec() -> None:
    with pytest.raises(NotImplementedError, match="azure-agent-framework"):
        get_backend("agent-framework", target="local")


def test_unsupported_target_names_supported_targets() -> None:
    with pytest.raises(UnsupportedTargetError, match="local"):
        get_backend("langgraph", target="cloud")


def test_unknown_target_names_the_choices() -> None:
    with pytest.raises(UnsupportedTargetError, match="container"):
        get_backend("langgraph", target="laptop")
