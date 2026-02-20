"""
Comprehensive unit tests for agents: BaseAgent, create_agent, roles, model assignment,
guardrail attachment, before/after_task hooks, and mocked Ollama LLM.
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_ollama import ChatOllama

from ai_team.agents.base import (
    BaseAgent,
    ROLE_TO_SETTINGS_KEY,
    create_agent,
    _load_agents_config,
)
from tests.unit.conftest import identity_llm


class TestBaseAgentInitializationWithRoles:
    """Test BaseAgent initialization with each role via create_agent."""

    @pytest.fixture
    def mock_llm(self) -> ChatOllama:
        return ChatOllama(model="qwen3:14b", base_url="http://localhost:11434")

    def test_create_agent_manager(
        self, agents_config_minimal: dict, mock_ollama_llm: ChatOllama
    ) -> None:
        with patch("ai_team.agents.base.get_settings") as mock_settings, patch(
            "ai_team.agents.base.LLM", return_value=mock_ollama_llm
        ), patch("crewai.agent.core.create_llm", side_effect=identity_llm):
            mock_settings.return_value.ollama.get_model_for_role.return_value = "qwen3:14b"
            mock_settings.return_value.ollama.base_url = "http://localhost:11434"
            mock_settings.return_value.ollama.request_timeout = 300
            mock_settings.return_value.ollama.max_retries = 3
            mock_settings.return_value.guardrails.security_enabled = False
            agent = create_agent(
                "manager",
                agents_config=agents_config_minimal,
                tools=[],
            )
        assert isinstance(agent, BaseAgent)
        assert agent.role_name == "manager"
        assert agent.role == "Engineering Manager"

    def test_create_agent_product_owner(
        self, agents_config_minimal: dict, mock_ollama_llm: ChatOllama
    ) -> None:
        with patch("ai_team.agents.base.get_settings") as mock_settings, patch(
            "ai_team.agents.base.LLM", return_value=mock_ollama_llm
        ), patch("crewai.agent.core.create_llm", side_effect=identity_llm):
            mock_settings.return_value.ollama.get_model_for_role.return_value = "qwen3:14b"
            mock_settings.return_value.ollama.base_url = "http://localhost:11434"
            mock_settings.return_value.ollama.request_timeout = 300
            mock_settings.return_value.ollama.max_retries = 3
            mock_settings.return_value.guardrails.security_enabled = False
            agent = create_agent(
                "product_owner",
                agents_config=agents_config_minimal,
                tools=[],
            )
        assert agent.role_name == "product_owner"
        assert agent.role == "Product Owner"

    def test_create_agent_architect_backend_qa(
        self, agents_config_minimal: dict, mock_ollama_llm: ChatOllama
    ) -> None:
        with patch("ai_team.agents.base.get_settings") as mock_settings, patch(
            "ai_team.agents.base.LLM", return_value=mock_ollama_llm
        ), patch("crewai.agent.core.create_llm", side_effect=identity_llm):
            mock_settings.return_value.ollama.get_model_for_role.return_value = "deepseek-r1:14b"
            mock_settings.return_value.ollama.base_url = "http://localhost:11434"
            mock_settings.return_value.ollama.request_timeout = 300
            mock_settings.return_value.ollama.max_retries = 3
            mock_settings.return_value.guardrails.security_enabled = False
            for role_name, expected_role in [
                ("architect", "Architect"),
                ("backend_developer", "Backend Developer"),
                ("qa_engineer", "QA Engineer"),
            ]:
                agent = create_agent(
                    role_name,
                    agents_config=agents_config_minimal,
                    tools=[],
                )
                assert agent.role_name == role_name
                assert agent.role == expected_role

    def test_create_agent_unknown_role_raises(self, agents_config_minimal: dict) -> None:
        with pytest.raises(KeyError, match="Unknown role_name"):
            create_agent("unknown_role", agents_config=agents_config_minimal)


class TestModelAssignmentFromSettings:
    """Test model assignment from settings per role."""

    def test_role_to_settings_key_mapping(self) -> None:
        assert ROLE_TO_SETTINGS_KEY["manager"] == "manager"
        assert ROLE_TO_SETTINGS_KEY["product_owner"] == "product_owner"
        assert ROLE_TO_SETTINGS_KEY["backend_developer"] == "backend_dev"
        assert ROLE_TO_SETTINGS_KEY["qa_engineer"] == "qa"
        assert ROLE_TO_SETTINGS_KEY["devops_engineer"] == "devops"
        assert ROLE_TO_SETTINGS_KEY["cloud_engineer"] == "cloud"

    def test_create_agent_calls_get_model_for_role(
        self, agents_config_minimal: dict, mock_ollama_llm: ChatOllama
    ) -> None:
        with patch("ai_team.agents.base.get_settings") as mock_settings, patch(
            "ai_team.agents.base.LLM", return_value=mock_ollama_llm
        ), patch("crewai.agent.core.create_llm", side_effect=identity_llm):
            mock_settings.return_value.ollama.get_model_for_role.return_value = "custom-model:7b"
            mock_settings.return_value.ollama.base_url = "http://localhost:11434"
            mock_settings.return_value.ollama.request_timeout = 300
            mock_settings.return_value.ollama.max_retries = 3
            mock_settings.return_value.guardrails.security_enabled = False
            create_agent("manager", agents_config=agents_config_minimal, tools=[])
            mock_settings.return_value.ollama.get_model_for_role.assert_called()
            call_args = mock_settings.return_value.ollama.get_model_for_role.call_args[0][0]
            assert call_args == "manager"


class TestGuardrailAttachment:
    """Test guardrail attachment to tools."""

    def test_guardrail_disabled_tools_not_wrapped(
        self, agents_config_minimal: dict, mock_ollama_llm: ChatOllama
    ) -> None:
        with patch("ai_team.agents.base.get_settings") as mock_settings, patch(
            "ai_team.agents.base.LLM", return_value=mock_ollama_llm
        ), patch("crewai.agent.core.create_llm", side_effect=identity_llm):
            mock_settings.return_value.ollama.get_model_for_role.return_value = "qwen3:14b"
            mock_settings.return_value.ollama.base_url = "http://localhost:11434"
            mock_settings.return_value.ollama.request_timeout = 300
            mock_settings.return_value.ollama.max_retries = 3
            mock_settings.return_value.guardrails.security_enabled = False
            agent = create_agent(
                "manager",
                agents_config=agents_config_minimal,
                tools=[],
                guardrail_tools=False,
            )
            assert len(agent.tools) == 0

    def test_guardrail_enabled_wraps_tools_when_security_on(
        self, agents_config_minimal: dict, mock_ollama_llm: ChatOllama
    ) -> None:
        from ai_team.tools.file_tools import get_file_tools

        real_tools = get_file_tools()
        if not real_tools:
            pytest.skip("No file tools available")
        with patch("ai_team.agents.base.get_settings") as mock_settings, patch(
            "ai_team.agents.base.LLM", return_value=mock_ollama_llm
        ), patch("crewai.agent.core.create_llm", side_effect=identity_llm):
            mock_settings.return_value.ollama.get_model_for_role.return_value = "qwen3:14b"
            mock_settings.return_value.ollama.base_url = "http://localhost:11434"
            mock_settings.return_value.ollama.request_timeout = 300
            mock_settings.return_value.ollama.max_retries = 3
            mock_settings.return_value.guardrails.security_enabled = True
            agent = create_agent(
                "manager",
                agents_config=agents_config_minimal,
                tools=real_tools[:1],
                guardrail_tools=True,
            )
            assert len(agent.tools) == 1


class TestBeforeTaskAfterTaskHooks:
    """Test before_task / after_task hook invocation."""

    def test_before_task_callback_invokes_hook(self, mock_ollama_llm: ChatOllama) -> None:
        hook = MagicMock()
        with patch("crewai.agent.core.create_llm", side_effect=identity_llm):
            agent = BaseAgent(
                role_name="manager",
                role="Manager",
                goal="Coordinate",
                backstory="Experienced",
                llm=mock_ollama_llm,
                tools=[],
                before_task=hook,
            )
        agent.before_task_callback("task_1", {"key": "value"})
        hook.assert_called_once_with("task_1", {"key": "value"})

    def test_after_task_callback_invokes_hook(self, mock_ollama_llm: ChatOllama) -> None:
        hook = MagicMock()
        with patch("crewai.agent.core.create_llm", side_effect=identity_llm):
            agent = BaseAgent(
                role_name="manager",
                role="Manager",
                goal="Coordinate",
                backstory="Experienced",
                llm=mock_ollama_llm,
                tools=[],
                after_task=hook,
            )
        agent.after_task_callback("task_1", "output text")
        hook.assert_called_once_with("task_1", "output text")

    def test_no_hook_does_not_raise(self, mock_ollama_llm: ChatOllama) -> None:
        with patch("crewai.agent.core.create_llm", side_effect=identity_llm):
            agent = BaseAgent(
                role_name="manager",
                role="Manager",
                goal="Coordinate",
                backstory="Experienced",
                llm=mock_ollama_llm,
                tools=[],
            )
        agent.before_task_callback("t", {})
        agent.after_task_callback("t", "out")


class TestMockOllamaLLM:
    """Tests that work with mocked Ollama LLM (no network)."""

    def test_token_usage_starts_zero(self, mock_ollama_llm: ChatOllama) -> None:
        with patch("crewai.agent.core.create_llm", side_effect=identity_llm):
            agent = BaseAgent(
                role_name="manager",
                role="Manager",
                goal="Coordinate",
                backstory="Experienced",
                llm=mock_ollama_llm,
                tools=[],
            )
        assert agent.token_usage["input_tokens"] == 0
        assert agent.token_usage["output_tokens"] == 0

    def test_record_tokens_updates_usage(self, mock_ollama_llm: ChatOllama) -> None:
        with patch("crewai.agent.core.create_llm", side_effect=identity_llm):
            agent = BaseAgent(
                role_name="manager",
                role="Manager",
                goal="Coordinate",
                backstory="Experienced",
                llm=mock_ollama_llm,
                tools=[],
            )
        agent.record_tokens(input_tokens=10, output_tokens=20)
        assert agent.token_usage["input_tokens"] == 10
        assert agent.token_usage["output_tokens"] == 20


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
