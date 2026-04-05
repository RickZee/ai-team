"""Tests for LangGraph TypedDict schemas and list/message reducers (T2.2)."""

from __future__ import annotations

from operator import add
from typing import Any

from ai_team.backends.langgraph_backend.graphs.state import LangGraphProjectState
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.message import add_messages


class TestOperatorAddReducers:
    def test_phase_history_merge(self) -> None:
        left: list[dict[str, Any]] = [{"from": "a", "to": "b"}]
        right: list[dict[str, Any]] = [{"from": "b", "to": "c"}]
        merged = add(left, right)
        assert len(merged) == 2
        assert merged[0]["to"] == "b"

    def test_errors_accumulate(self) -> None:
        e1 = [{"type": "E1", "message": "m1"}]
        e2 = [{"type": "E2", "message": "m2"}]
        assert add(e1, e2) == e1 + e2

    def test_generated_files_concat(self) -> None:
        a = [{"path": "a.py", "content": "1"}]
        b = [{"path": "b.py", "content": "2"}]
        assert add(a, b)[1]["path"] == "b.py"


class TestAddMessagesReducer:
    def test_concatenates_message_lists(self) -> None:
        m1 = [HumanMessage(content="hello")]
        m2 = [AIMessage(content="world")]
        out = add_messages(m1, m2)
        assert len(out) == 2
        assert out[0].content == "hello"
        assert out[1].content == "world"


class TestLangGraphProjectStateShape:
    def test_can_build_minimal_state_dict(self) -> None:
        s: LangGraphProjectState = {
            "project_description": "Build API",
            "project_id": "p-1",
            "current_phase": "intake",
            "phase_history": [],
            "messages": [],
            "retry_count": 0,
            "max_retries": 3,
        }
        assert s["current_phase"] == "intake"
