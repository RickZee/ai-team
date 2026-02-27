"""Unit tests for DevOps and Cloud agents and their tools."""

import pytest
from unittest.mock import MagicMock, patch

from ai_team.agents.base import BaseAgent
from ai_team.agents.devops_engineer import create_devops_engineer, DevOpsEngineer
from ai_team.agents.cloud_engineer import create_cloud_engineer, CloudEngineer
from ai_team.tools.infrastructure import (
    DEVOPS_TOOLS,
    CLOUD_TOOLS,
    dockerfile_generator,
    terraform_generator,
)
from ai_team.guardrails import SecurityGuardrails


def _identity_llm(llm: object) -> object:
    """Pass-through so CrewAI uses our LLM as-is in tests."""
    return llm


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.model = "openrouter/deepseek/deepseek-chat-v3-0324"
    return llm


@pytest.fixture
def infra_config() -> dict:
    return {
        "devops_engineer": {
            "role": "DevOps / SRE Engineer",
            "goal": "Design CI/CD, Docker, K8s, monitoring.",
            "backstory": "SRE from Netflix/Google/Spotify.",
            "verbose": True,
            "allow_delegation": False,
            "max_iter": 10,
            "memory": True,
        },
        "cloud_engineer": {
            "role": "Cloud Infrastructure Engineer",
            "goal": "Design cloud infra with IaC.",
            "backstory": "Multi-cloud certified.",
            "verbose": True,
            "allow_delegation": False,
            "max_iter": 10,
            "memory": True,
        },
    }


class TestDevOpsEngineer:
    def test_create_devops_engineer_returns_base_agent(
        self, mock_llm, infra_config: dict
    ) -> None:
        with patch("ai_team.agents.base.get_settings") as mock_settings, patch(
            "ai_team.agents.base.create_llm_for_role", return_value=mock_llm
        ), patch("crewai.agent.core.create_llm", side_effect=_identity_llm):
            mock_settings.return_value.guardrails.security_enabled = False
            agent = create_devops_engineer(agents_config=infra_config)
            assert isinstance(agent, BaseAgent)
            assert agent.role_name == "devops_engineer"
            assert agent.role == "DevOps / SRE Engineer"
            assert agent.allow_delegation is False
            assert agent.max_iter == 10
            assert len(agent.tools) == len(DEVOPS_TOOLS)

    def test_devops_engineer_alias(self) -> None:
        assert create_devops_engineer is DevOpsEngineer


class TestCloudEngineer:
    def test_create_cloud_engineer_returns_base_agent(
        self, mock_llm, infra_config: dict
    ) -> None:
        with patch("ai_team.agents.base.get_settings") as mock_settings, patch(
            "ai_team.agents.base.create_llm_for_role", return_value=mock_llm
        ), patch("crewai.agent.core.create_llm", side_effect=_identity_llm):
            mock_settings.return_value.guardrails.security_enabled = False
            agent = create_cloud_engineer(agents_config=infra_config)
            assert isinstance(agent, BaseAgent)
            assert agent.role_name == "cloud_engineer"
            assert agent.role == "Cloud Infrastructure Engineer"
            assert agent.allow_delegation is False
            assert agent.max_iter == 10
            assert len(agent.tools) == len(CLOUD_TOOLS)

    def test_cloud_engineer_alias(self) -> None:
        assert create_cloud_engineer is CloudEngineer


class TestInfrastructureTools:
    def test_dockerfile_generator_includes_user_and_healthcheck(self) -> None:
        out = dockerfile_generator.run(spec="Python API")
        assert "USER " in out
        assert "HEALTHCHECK" in out
        assert "python" in out.lower()

    def test_dockerfile_generator_passes_iac_validation(self) -> None:
        out = dockerfile_generator.run(spec="FastAPI app")
        valid, _ = SecurityGuardrails.validate_iac_security(out, "dockerfile")
        assert valid

    def test_terraform_generator_passes_iac_validation(self) -> None:
        out = terraform_generator.run(spec="S3 bucket and Lambda")
        valid, _ = SecurityGuardrails.validate_iac_security(out, "terraform")
        assert valid
