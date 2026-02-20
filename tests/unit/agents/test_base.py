"""Unit tests for BaseAgent and create_agent factory."""

import pytest
from unittest.mock import MagicMock, patch

from langchain_ollama import ChatOllama

from ai_team.agents.base import (
    BaseAgent,
    create_agent,
    ROLE_TO_SETTINGS_KEY,
    _load_agents_config,
)


def _identity_llm(llm: object) -> object:
    """Pass-through so CrewAI uses our LLM as-is in tests."""
    return llm


class TestRoleMapping:
    """Test role name to settings key mapping."""

    def test_known_roles_mapped(self) -> None:
        assert ROLE_TO_SETTINGS_KEY["manager"] == "manager"
        assert ROLE_TO_SETTINGS_KEY["backend_developer"] == "backend_dev"
        assert ROLE_TO_SETTINGS_KEY["qa_engineer"] == "qa"


class TestLoadAgentsConfig:
    """Test YAML config loading."""

    def test_load_agents_config_returns_dict(self) -> None:
        config = _load_agents_config()
        assert isinstance(config, dict)
        assert "manager" in config
        assert "backend_developer" in config

    def test_manager_config_has_required_keys(self) -> None:
        config = _load_agents_config()
        manager = config["manager"]
        assert "role" in manager
        assert "goal" in manager
        assert "backstory" in manager


class TestCreateAgent:
    """Test create_agent factory."""

    @pytest.fixture
    def mock_llm(self) -> ChatOllama:
        """Real ChatOllama instance so CrewAI accepts it; no network if not invoked."""
        return ChatOllama(model="qwen3:14b", base_url="http://localhost:11434")

    @pytest.fixture
    def minimal_config(self) -> dict:
        return {
            "manager": {
                "role": "Engineering Manager",
                "goal": "Coordinate the team.",
                "backstory": "Experienced leader.",
                "verbose": True,
                "allow_delegation": True,
                "max_iter": 15,
                "memory": True,
            },
        }

    def test_create_agent_from_dict_returns_base_agent(
        self, minimal_config: dict, mock_llm: ChatOllama
    ) -> None:
        with patch("ai_team.agents.base.get_settings") as mock_settings, patch(
            "ai_team.agents.base.LLM", return_value=mock_llm
        ), patch("crewai.agent.core.create_llm", side_effect=_identity_llm):
            mock_settings.return_value.ollama.get_model_for_role.return_value = "qwen3:14b"
            mock_settings.return_value.ollama.base_url = "http://localhost:11434"
            mock_settings.return_value.ollama.request_timeout = 300
            mock_settings.return_value.ollama.max_retries = 3
            mock_settings.return_value.guardrails.security_enabled = False
            agent = create_agent(
                "manager",
                agents_config=minimal_config,
                tools=[],
            )
            assert isinstance(agent, BaseAgent)
            assert agent.role_name == "manager"
            assert agent.role == "Engineering Manager"

    def test_create_agent_unknown_role_raises(self, minimal_config: dict) -> None:
        with pytest.raises(KeyError, match="Unknown role_name"):
            create_agent("unknown_role", agents_config=minimal_config)


class TestBaseAgent:
    """Test BaseAgent behavior."""

    @pytest.fixture
    def mock_llm(self) -> ChatOllama:
        """Real ChatOllama so CrewAI accepts it; no network if not invoked."""
        return ChatOllama(model="qwen3:14b", base_url="http://localhost:11434")

    def test_token_usage_starts_zero(self, mock_llm: ChatOllama) -> None:
        with patch("crewai.agent.core.create_llm", side_effect=_identity_llm):
            agent = BaseAgent(
                role_name="manager",
                role="Manager",
                goal="Coordinate",
                backstory="Experienced",
                llm=mock_llm,
                tools=[],
            )
        assert agent.token_usage["input_tokens"] == 0
        assert agent.token_usage["output_tokens"] == 0

    def test_record_tokens_updates_usage(self, mock_llm: ChatOllama) -> None:
        with patch("crewai.agent.core.create_llm", side_effect=_identity_llm):
            agent = BaseAgent(
                role_name="manager",
                role="Manager",
                goal="Coordinate",
                backstory="Experienced",
                llm=mock_llm,
                tools=[],
            )
        agent.record_tokens(input_tokens=10, output_tokens=20)
        assert agent.token_usage["input_tokens"] == 10
        assert agent.token_usage["output_tokens"] == 20
        agent.record_tokens(input_tokens=5, output_tokens=5)
        assert agent.token_usage["input_tokens"] == 15
        assert agent.token_usage["output_tokens"] == 25

    def test_before_task_callback_invokes_hook(self, mock_llm: ChatOllama) -> None:
        hook = MagicMock()
        with patch("crewai.agent.core.create_llm", side_effect=_identity_llm):
            agent = BaseAgent(
                role_name="manager",
                role="Manager",
                goal="Coordinate",
                backstory="Experienced",
                llm=mock_llm,
                tools=[],
                before_task=hook,
            )
        agent.before_task_callback("task_1", {"key": "value"})
        hook.assert_called_once_with("task_1", {"key": "value"})

    def test_after_task_callback_invokes_hook(self, mock_llm: ChatOllama) -> None:
        hook = MagicMock()
        with patch("crewai.agent.core.create_llm", side_effect=_identity_llm):
            agent = BaseAgent(
                role_name="manager",
                role="Manager",
                goal="Coordinate",
                backstory="Experienced",
                llm=mock_llm,
                tools=[],
                after_task=hook,
            )
        agent.after_task_callback("task_1", "output text")
        hook.assert_called_once_with("task_1", "output text")

    def test_health_check_uses_ollama_settings(self, mock_llm: ChatOllama) -> None:
        with patch("crewai.agent.core.create_llm", side_effect=_identity_llm):
            agent = BaseAgent(
                role_name="manager",
                role="Manager",
                goal="Coordinate",
                backstory="Experienced",
                llm=mock_llm,
                tools=[],
            )
        with patch("ai_team.agents.base.get_settings") as mock_settings:
            mock_settings.return_value.ollama.check_health.return_value = True
            mock_settings.return_value.ollama.base_url = "http://localhost:11434"
            with patch("httpx.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {
                    "models": [{"name": "qwen3:14b"}],
                }
                # CrewAI 0.80 wraps llm and model may be repr; force .model so health_check's check passes
                llm_with_model = MagicMock()
                llm_with_model.model = "qwen3:14b"
                object.__setattr__(agent, "llm", llm_with_model)
                assert agent.health_check() is True
