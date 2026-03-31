"""Verify that compile_*_subgraph functions filter agents based on profile."""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

from .stub_chat_model import FakeChatModelWithBindTools

STUB = FakeListChatModel(responses=["Stub reply."])
MULTI_STUB = FakeChatModelWithBindTools(responses=["ok"] * 120)
BASE_INPUT = {
    "messages": [HumanMessage("test")],
    "guardrail_checks": [],
    "project_description": "x" * 30,
    "requirements": {},
    "architecture": {},
}


def _no_tools(_role: str) -> list:
    return []


class TestPlanningSubgraphFiltering:
    def test_full_agents_creates_supervisor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.planning.get_langchain_tools_for_role",
            _no_tools,
        )
        from ai_team.backends.langgraph_backend.graphs.planning import (
            compile_planning_subgraph,
        )

        g = compile_planning_subgraph(
            agents=frozenset({"manager", "product_owner", "architect"}),
            manager_llm=MULTI_STUB,
            product_owner_llm=MULTI_STUB,
            architect_llm=MULTI_STUB,
        )
        out = g.invoke(BASE_INPUT)
        assert "messages" in out

    def test_single_worker_creates_react_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.planning.get_langchain_tools_for_role",
            _no_tools,
        )
        from ai_team.backends.langgraph_backend.graphs.planning import (
            compile_planning_subgraph,
        )

        g = compile_planning_subgraph(
            agents=frozenset({"architect"}),
            architect_llm=STUB,
        )
        out = g.invoke(BASE_INPUT)
        assert "messages" in out

    def test_no_workers_creates_passthrough(self) -> None:
        from ai_team.backends.langgraph_backend.graphs.planning import (
            compile_planning_subgraph,
        )

        g = compile_planning_subgraph(agents=frozenset({"backend_developer"}))
        out = g.invoke(BASE_INPUT)
        assert "messages" in out

    def test_agents_none_means_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.planning.get_langchain_tools_for_role",
            _no_tools,
        )
        from ai_team.backends.langgraph_backend.graphs.planning import (
            compile_planning_subgraph,
        )

        g = compile_planning_subgraph(
            agents=None,
            manager_llm=MULTI_STUB,
            product_owner_llm=MULTI_STUB,
            architect_llm=MULTI_STUB,
        )
        out = g.invoke(BASE_INPUT)
        assert "messages" in out


class TestDevelopmentSubgraphFiltering:
    def test_backend_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.development.get_langchain_tools_for_role",
            _no_tools,
        )
        from ai_team.backends.langgraph_backend.graphs.development import (
            compile_development_subgraph,
        )

        g = compile_development_subgraph(
            agents=frozenset({"backend_developer"}),
            backend_llm=STUB,
        )
        out = g.invoke(BASE_INPUT)
        assert "messages" in out

    def test_no_dev_workers_passthrough(self) -> None:
        from ai_team.backends.langgraph_backend.graphs.development import (
            compile_development_subgraph,
        )

        g = compile_development_subgraph(agents=frozenset({"qa_engineer"}))
        out = g.invoke(BASE_INPUT)
        assert "messages" in out

    def test_two_workers_creates_supervisor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.development.get_langchain_tools_for_role",
            _no_tools,
        )
        from ai_team.backends.langgraph_backend.graphs.development import (
            compile_development_subgraph,
        )

        g = compile_development_subgraph(
            agents=frozenset({"backend_developer", "frontend_developer"}),
            manager_llm=MULTI_STUB,
            backend_llm=MULTI_STUB,
            frontend_llm=MULTI_STUB,
        )
        out = g.invoke(BASE_INPUT)
        assert "messages" in out


class TestTestingSubgraphFiltering:
    def test_qa_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.testing.get_langchain_tools_for_role",
            _no_tools,
        )
        from ai_team.backends.langgraph_backend.graphs.testing import (
            compile_testing_subgraph,
        )

        g = compile_testing_subgraph(
            agents=frozenset({"qa_engineer"}),
            qa_llm=STUB,
        )
        out = g.invoke(BASE_INPUT)
        assert "messages" in out

    def test_qa_absent_passthrough(self) -> None:
        from ai_team.backends.langgraph_backend.graphs.testing import (
            compile_testing_subgraph,
        )

        g = compile_testing_subgraph(agents=frozenset({"backend_developer"}))
        out = g.invoke(BASE_INPUT)
        assert "messages" in out


class TestDeploymentSubgraphFiltering:
    def test_devops_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.deployment.get_langchain_tools_for_role",
            _no_tools,
        )
        from ai_team.backends.langgraph_backend.graphs.deployment import (
            compile_deployment_subgraph,
        )

        g = compile_deployment_subgraph(
            agents=frozenset({"devops_engineer"}),
            devops_llm=STUB,
        )
        out = g.invoke(BASE_INPUT)
        assert "messages" in out

    def test_no_deployment_workers_passthrough(self) -> None:
        from ai_team.backends.langgraph_backend.graphs.deployment import (
            compile_deployment_subgraph,
        )

        g = compile_deployment_subgraph(agents=frozenset({"qa_engineer"}))
        out = g.invoke(BASE_INPUT)
        assert "messages" in out

    def test_both_workers_sequential(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.deployment.get_langchain_tools_for_role",
            _no_tools,
        )
        from ai_team.backends.langgraph_backend.graphs.deployment import (
            compile_deployment_subgraph,
        )

        g = compile_deployment_subgraph(
            agents=frozenset({"devops_engineer", "cloud_engineer"}),
            devops_llm=STUB,
            cloud_llm=STUB,
        )
        out = g.invoke(BASE_INPUT)
        assert "messages" in out
