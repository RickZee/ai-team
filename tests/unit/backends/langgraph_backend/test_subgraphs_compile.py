"""Compile LangGraph subgraphs with stub LLMs (empty tools) or smoke checks."""

from __future__ import annotations

import pytest
from ai_team.backends.langgraph_backend.graphs.deployment import (
    compile_deployment_subgraph,
)
from ai_team.backends.langgraph_backend.graphs.development import (
    compile_development_subgraph,
)
from ai_team.backends.langgraph_backend.graphs.guardrail_hooks import (
    planning_guardrail_result,
)
from ai_team.backends.langgraph_backend.graphs.planning import compile_planning_subgraph
from ai_team.backends.langgraph_backend.graphs.testing import compile_testing_subgraph
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

from .stub_chat_model import FakeChatModelWithBindTools


@pytest.fixture
def stub_llm() -> FakeListChatModel:
    return FakeListChatModel(responses=["Stub assistant reply for testing."])


@pytest.fixture
def multi_turn_stub_llm() -> FakeChatModelWithBindTools:
    """Enough turns for supervisor + ReAct workers without real tools."""
    return FakeChatModelWithBindTools(responses=["ok"] * 120)


def test_planning_guardrail_on_empty_messages() -> None:
    gr = planning_guardrail_result({"messages": []})
    assert gr.status == "pass"


def test_testing_subgraph_compiles_with_stub(
    monkeypatch: pytest.MonkeyPatch,
    stub_llm: FakeListChatModel,
) -> None:
    monkeypatch.setattr(
        "ai_team.backends.langgraph_backend.graphs.testing.get_langchain_tools_for_role",
        lambda _role: [],
    )
    g = compile_testing_subgraph(qa_llm=stub_llm)
    out = g.invoke(
        {
            "messages": [HumanMessage("Run QA checks.")],
            "guardrail_checks": [],
        }
    )
    assert "messages" in out


def test_deployment_subgraph_compiles_with_stub(
    monkeypatch: pytest.MonkeyPatch,
    stub_llm: FakeListChatModel,
) -> None:
    monkeypatch.setattr(
        "ai_team.backends.langgraph_backend.graphs.deployment.get_langchain_tools_for_role",
        lambda _role: [],
    )
    g = compile_deployment_subgraph(devops_llm=stub_llm, cloud_llm=stub_llm)
    out = g.invoke(
        {
            "messages": [HumanMessage("Deploy the service.")],
            "guardrail_checks": [],
        }
    )
    assert "messages" in out


def test_planning_subgraph_compiles_with_stub(
    monkeypatch: pytest.MonkeyPatch,
    multi_turn_stub_llm: FakeListChatModel,
) -> None:
    """Planning supervisor + PO + Architect compile and invoke with fake chat model."""
    monkeypatch.setattr(
        "ai_team.backends.langgraph_backend.graphs.planning.get_langchain_tools_for_role",
        lambda _role: [],
    )
    g = compile_planning_subgraph(
        manager_llm=multi_turn_stub_llm,
        product_owner_llm=multi_turn_stub_llm,
        architect_llm=multi_turn_stub_llm,
    )
    out = g.invoke(
        {
            "messages": [HumanMessage("Plan a minimal REST API.")],
            "guardrail_checks": [],
            "project_description": "x" * 30,
        }
    )
    assert "messages" in out


def test_development_subgraph_compiles_with_stub(
    monkeypatch: pytest.MonkeyPatch,
    multi_turn_stub_llm: FakeListChatModel,
) -> None:
    """Development supervisor + dev workers compile and invoke with fake chat model."""
    monkeypatch.setattr(
        "ai_team.backends.langgraph_backend.graphs.development.get_langchain_tools_for_role",
        lambda _role: [],
    )
    g = compile_development_subgraph(
        manager_llm=multi_turn_stub_llm,
        backend_llm=multi_turn_stub_llm,
        frontend_llm=multi_turn_stub_llm,
        fullstack_llm=multi_turn_stub_llm,
    )
    out = g.invoke(
        {
            "messages": [HumanMessage("Implement the service layer.")],
            "guardrail_checks": [],
            "project_description": "x" * 30,
            "requirements": {},
            "architecture": {},
        }
    )
    assert "messages" in out
