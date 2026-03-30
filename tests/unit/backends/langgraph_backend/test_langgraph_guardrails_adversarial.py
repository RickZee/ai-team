"""
Adversarial-style tests for LangGraph guardrail nodes (mirrors ``tests/unit/test_guardrails.py`` cases).

Uses synthetic ``AIMessage`` / ``HumanMessage`` state instead of full subgraph LLM runs.
"""

from __future__ import annotations

from typing import cast

from ai_team.backends.langgraph_backend.graphs.langgraph_guardrail_nodes import (
    make_behavioral_guardrail_node,
    quality_guardrail_node,
    security_guardrail_node,
)
from ai_team.backends.langgraph_backend.graphs.state import LangGraphSubgraphState
from langchain_core.messages import AIMessage, HumanMessage


def _state_with_ai(text: str, **extra: object) -> LangGraphSubgraphState:
    base: LangGraphSubgraphState = {
        "messages": [HumanMessage("User"), AIMessage(content=text)],
        "guardrail_checks": [],
    }
    for k, v in extra.items():
        base[k] = v  # type: ignore[literal-required]
    return base


class TestLangGraphBehavioralNodeAdversarial:
    def test_qa_passes_tests_only(self) -> None:
        node = make_behavioral_guardrail_node("qa_engineer")
        out = node(_state_with_ai("def test_login(): assert login() is True"))
        checks = out["guardrail_checks"]
        assert checks[-1]["phase"] == "behavioral"
        assert checks[-1]["status"] == "pass"

    def test_qa_fails_production_code(self) -> None:
        node = make_behavioral_guardrail_node("qa_engineer")
        out = node(
            _state_with_ai(
                "def get_user(user_id: int): return db.query(User).get(user_id)"
            )
        )
        assert out["guardrail_checks"][-1]["status"] == "fail"

    def test_scope_fail_off_scope(self) -> None:
        node = make_behavioral_guardrail_node("manager")
        out = node(
            _state_with_ai(
                "The weather is sunny. Frogs are amphibians.",
                project_description="Implement user login and session management.",
            )
        )
        assert out["guardrail_checks"][-1]["status"] == "fail"

    def test_manager_filtered_skips_worker_code(self) -> None:
        """Supervisor planning: do not apply manager rules to architect/PO messages."""
        state = cast(
            LangGraphSubgraphState,
            {
                "messages": [
                    HumanMessage("Build an API"),
                    AIMessage(
                        content="import flask\nclass App:\n    pass",
                        name="architect",
                    ),
                    AIMessage(
                        content="Thanks — I've delegated design. Next we'll refine acceptance criteria.",
                        name="planning_supervisor",
                    ),
                ],
                "guardrail_checks": [],
            },
        )
        unfiltered = make_behavioral_guardrail_node("manager")
        assert unfiltered(state)["guardrail_checks"][-1]["status"] == "fail"

        filtered = make_behavioral_guardrail_node(
            "manager",
            behavioral_only_message_names=frozenset({"planning_supervisor"}),
        )
        assert filtered(state)["guardrail_checks"][-1]["status"] == "pass"


class TestLangGraphSecurityNodeAdversarial:
    def test_fail_eval(self) -> None:
        out = security_guardrail_node(_state_with_ai("x = eval(user_input)"))
        assert out["guardrail_checks"][-1]["status"] == "fail"

    def test_fail_exec(self) -> None:
        out = security_guardrail_node(_state_with_ai("exec(code)"))
        assert out["guardrail_checks"][-1]["status"] == "fail"

    def test_fail_secret_api_key(self) -> None:
        out = security_guardrail_node(_state_with_ai("api_key = 'sk-1234567890abcdef'"))
        assert out["guardrail_checks"][-1]["status"] in ("fail", "warn")


class TestLangGraphQualityNodeAdversarial:
    def test_warn_syntax(self) -> None:
        out = quality_guardrail_node(
            _state_with_ai("```python\ndef broken( \n```", project_description="")
        )
        assert out["guardrail_checks"][-1]["status"] == "warn"

    def test_pass_good_python(self) -> None:
        code = '''```python
"""Doc."""
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
```'''
        out = quality_guardrail_node(_state_with_ai(code))
        assert out["guardrail_checks"][-1]["status"] == "pass"

    def test_skips_unfenced_code(self) -> None:
        out = quality_guardrail_node(
            _state_with_ai("We should def add(a, b) to handle items", project_description="")
        )
        assert out["guardrail_checks"][-1]["status"] == "pass"

    def test_skips_prose_stub(self) -> None:
        """Conversational stubs must not fail ``ast.parse`` in quality."""
        out = quality_guardrail_node(
            _state_with_ai("Stub assistant reply for testing.")
        )
        assert out["guardrail_checks"][-1]["status"] == "pass"
