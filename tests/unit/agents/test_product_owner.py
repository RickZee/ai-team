"""Unit tests for Product Owner agent, tools, and validation."""

import pytest

from ai_team.agents.product_owner import (
    create_product_owner_agent,
    get_template_for_project_type,
    requirements_from_agent_output,
    validate_requirements_document,
)
from ai_team.agents.base import BaseAgent
from ai_team.models.requirements import (
    AcceptanceCriterion,
    MoSCoW,
    RequirementsDocument,
    UserStory,
)
from ai_team.tools.product_owner import validate_requirements_guardrail


class TestValidateRequirementsGuardrail:
    """Test guardrail: reject vague or contradictory requirements."""

    def test_rejects_vague(self) -> None:
        valid, msg = validate_requirements_guardrail("We need something better maybe")
        assert valid is False
        assert "vague" in msg.lower()

    def test_rejects_contradictions(self) -> None:
        valid, msg = validate_requirements_guardrail("This is required but optional")
        assert valid is False
        assert "contradiction" in msg.lower()

    def test_accepts_clear(self) -> None:
        valid, msg = validate_requirements_guardrail("User can log in with email and password")
        assert valid is True
        assert msg == "OK"


class TestValidateRequirementsDocument:
    """Test self-validation of RequirementsDocument."""

    def test_valid_document_passes(self) -> None:
        doc = RequirementsDocument(
            project_name="Test",
            description="A test project",
            user_stories=[
                UserStory(
                    as_a="user",
                    i_want="to log in",
                    so_that="I can access my account",
                    acceptance_criteria=[
                        AcceptanceCriterion(description="Given credentials, when valid, then access granted.", testable=True)
                    ],
                    priority=MoSCoW.MUST,
                )
            ],
        )
        valid, errors = validate_requirements_document(doc)
        assert valid is True
        assert errors == []

    def test_missing_acceptance_criteria_fails(self) -> None:
        doc = RequirementsDocument(
            project_name="P",
            description="D",
            user_stories=[
                UserStory(as_a="u", i_want="x", so_that="y", acceptance_criteria=[], priority=MoSCoW.MUST)
            ],
        )
        valid, errors = validate_requirements_document(doc)
        assert valid is False
        assert any("acceptance" in e for e in errors)


class TestGetTemplateForProjectType:
    """Test project type templates."""

    def test_api_template(self) -> None:
        t = get_template_for_project_type("api")
        assert "REST" in t or "API" in t

    def test_unknown_returns_generic(self) -> None:
        t = get_template_for_project_type("unknown")
        assert "target users" in t or "generic" in t.lower()


class TestRequirementsFromAgentOutput:
    """Test parsing agent output into RequirementsDocument."""

    def test_parse_json_block(self) -> None:
        raw = '''Some text
```json
{
  "project_name": "My API",
  "description": "REST API for X",
  "target_users": ["developers"],
  "user_stories": [
    {
      "as_a": "developer",
      "i_want": "an endpoint",
      "so_that": "I can integrate",
      "acceptance_criteria": [{"description": "GET returns 200", "testable": true}],
      "priority": "Must have"
    }
  ],
  "non_functional_requirements": [],
  "assumptions": [],
  "constraints": []
}
```
'''
        doc, errors = requirements_from_agent_output(raw)
        assert doc is not None
        assert doc.project_name == "My API"
        assert len(doc.user_stories) == 1
        assert doc.user_stories[0].as_a == "developer"
        assert errors == []

    def test_fallback_minimal_document(self) -> None:
        doc, errors = requirements_from_agent_output("Just narrative.", project_name="P", description="D")
        assert doc is not None
        assert doc.project_name == "P"
        assert len(doc.user_stories) == 1
        assert errors == []


class TestCreateProductOwnerAgent:
    """Test Product Owner agent creation."""

    @pytest.fixture
    def minimal_config(self) -> dict:
        return {
            "product_owner": {
                "role": "Product Owner / Requirements Analyst",
                "goal": "Transform vague ideas into clear requirements.",
                "backstory": "Expert in MoSCoW.",
                "verbose": True,
                "allow_delegation": False,
                "max_iter": 10,
                "memory": True,
            },
        }

    def test_returns_base_agent(self, minimal_config: dict) -> None:
        from unittest.mock import patch
        from langchain_ollama import ChatOllama

        def _identity_llm(llm: object) -> object:
            return llm

        mock_llm = ChatOllama(model="qwen3:14b", base_url="http://localhost:11434")
        with patch("ai_team.agents.base.get_settings") as mock_settings, patch(
            "ai_team.agents.base.LLM", return_value=mock_llm
        ), patch("crewai.agent.core.create_llm", side_effect=_identity_llm):
            mock_settings.return_value.ollama.get_model_for_role.return_value = "qwen3:14b"
            mock_settings.return_value.ollama.base_url = "http://localhost:11434"
            mock_settings.return_value.ollama.request_timeout = 300
            mock_settings.return_value.ollama.max_retries = 3
            mock_settings.return_value.guardrails.security_enabled = False
            agent = create_product_owner_agent(tools=[], agents_config=minimal_config)
        assert isinstance(agent, BaseAgent)
        assert agent.role_name == "product_owner"
        assert "Requirements" in agent.role or "Product Owner" in agent.role
