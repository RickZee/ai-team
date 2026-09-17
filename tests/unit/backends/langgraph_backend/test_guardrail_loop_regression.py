"""Regression: the 2026-09-13 LangGraph smoke loop (1,600 s on a 1.5 s task → HITL).

Four defects, each pinned here:

1. Guardrails scored the last 12 messages of the *seeded run history*, so the QA agent
   was judged on the architect's ADR and scored 0–9% relevance against a 15% floor.
2. Single-agent planning/development subgraphs filtered on a supervisor name that did
   not exist, so their behavioral guardrail passed vacuously.
3. A testing-phase ``GuardrailError`` routed to ``retry_development``, turning one QA
   complaint into full dev+test cycles.
4. The testing node and the file inventory used the parent ``./workspace`` tree instead
   of the run's own workspace.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ai_team.backends.langgraph_backend.graphs import development, planning
from ai_team.backends.langgraph_backend.graphs import subgraph_runners as sr
from ai_team.backends.langgraph_backend.graphs.guardrail_hooks import (
    concat_recent_ai_content,
    current_turn,
)
from ai_team.backends.langgraph_backend.graphs.langgraph_guardrail_nodes import (
    _CODE_ROLE_SCOPE_RELEVANCE,
    _behavioral_stack,
    make_behavioral_guardrail_node,
)
from ai_team.backends.langgraph_backend.graphs.routing import route_after_testing
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage

DESC = (
    "Write a single Python module calc.py with add, subtract, multiply and divide "
    "functions and a pytest test file."
)
ADR = AIMessage(
    content=(
        "# ADR-001: Module layout\n\nContext: stakeholders require maintainability, "
        "observability, deployment topology, container orchestration strategy, stateless "
        "microservice boundaries, horizontal scaling, infrastructure-as-code governance and "
        "cross-functional alignment on non-functional requirements. "
    )
    * 4,
    name="architect",
)
QA_CODE = AIMessage(
    content="```python\nimport pytest\nfrom calc import add\n\ndef test_add():\n"
    "    assert add(2, 3) == 5\n```",
    name="qa_engineer",
)


def _qa_state() -> dict[str, Any]:
    return {
        "project_description": DESC,
        "messages": [
            HumanMessage(content=DESC),
            ADR,
            AIMessage(content="Implementation committed; handing off to QA.", name="dev"),
            HumanMessage(content="Your task: write pytest tests using file_writer."),
            QA_CODE,
        ],
    }


class TestScoreTheCurrentTurn:
    def test_current_turn_is_everything_after_the_last_human_message(self) -> None:
        msgs = _qa_state()["messages"]
        assert current_turn(msgs) == [QA_CODE]
        assert current_turn([ADR, QA_CODE]) == [ADR, QA_CODE]
        assert current_turn([HumanMessage(content="x")]) == []

    def test_history_scoring_reproduces_the_false_failure(self) -> None:
        """The old input (whole seeded history) fails correct QA output."""
        old_text = concat_recent_ai_content(_qa_state()["messages"])
        gr = _behavioral_stack(
            old_text, "qa_engineer", DESC, min_scope_relevance=_CODE_ROLE_SCOPE_RELEVANCE
        )
        assert gr.status == "fail"
        assert "deviates from task scope" in gr.message

    def test_behavioral_node_judges_only_the_qa_turn(self) -> None:
        node = make_behavioral_guardrail_node(
            "qa_engineer", min_scope_relevance=_CODE_ROLE_SCOPE_RELEVANCE
        )
        check = node(_qa_state())["guardrail_checks"][0]
        assert check["status"] != "fail", check

    def test_off_topic_current_turn_still_fails(self) -> None:
        state = _qa_state()
        state["messages"] = [
            *state["messages"][:-1],
            AIMessage(
                content="The weather in Lisbon is sunny today and the tapas restaurants "
                "near the harbour are excellent for a long relaxed lunch with friends.",
                name="qa_engineer",
            ),
        ]
        node = make_behavioral_guardrail_node(
            "qa_engineer", min_scope_relevance=_CODE_ROLE_SCOPE_RELEVANCE
        )
        assert node(state)["guardrail_checks"][0]["status"] == "fail"


class TestSingleAgentIsNotASupervisor:
    @pytest.mark.parametrize(
        ("module", "compile_name", "agents", "llm_kw"),
        [
            (planning, "compile_planning_subgraph", {"architect"}, "architect_llm"),
            (
                development,
                "compile_development_subgraph",
                {"fullstack_developer"},
                "fullstack_llm",
            ),
        ],
    )
    def test_single_agent_has_no_supervisor_filter(
        self,
        monkeypatch: pytest.MonkeyPatch,
        module: Any,
        compile_name: str,
        agents: set[str],
        llm_kw: str,
    ) -> None:
        seen: dict[str, Any] = {}

        def _capture(core: Any, **kw: Any) -> Any:
            seen.update(kw)
            return core

        monkeypatch.setattr(module, "wrap_agents_with_guardrails", _capture)
        monkeypatch.setattr(module, "get_langchain_tools_for_role", lambda _r: [])
        llm = FakeListChatModel(responses=["ok"])
        getattr(module, compile_name)(agents=frozenset(agents), **{llm_kw: llm})
        assert seen["behavioral_only_message_names"] is None
        assert seen["behavioral_role"] == next(iter(agents))


class TestGuardrailErrorDoesNotRetryDevelopment:
    def test_testing_guardrail_error_goes_to_human(self) -> None:
        state = {
            "errors": [{"phase": "testing", "type": "GuardrailError", "message": "scope"}],
            "retry_count": 0,
            "max_retries": 3,
        }
        assert route_after_testing(state) == "human_review"

    def test_testing_crash_still_retries(self) -> None:
        state = {
            "errors": [{"phase": "testing", "type": "JSONDecodeError", "message": "bad"}],
            "retry_count": 0,
            "max_retries": 3,
        }
        assert route_after_testing(state) == "retry_development"


class TestRunScopedWorkspace:
    def test_testing_prompt_and_inventory_use_the_run_workspace(self, tmp_path: Any) -> None:
        from ai_team.config.settings import scoped_workspace_dir

        run_ws = tmp_path / "workspace" / "run-1"
        run_ws.mkdir(parents=True)
        (run_ws / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (tmp_path / "workspace" / "other-run.txt").write_text("x", encoding="utf-8")

        sub = MagicMock()
        sub.invoke.return_value = {"messages": [AIMessage(content="done")]}
        with (
            scoped_workspace_dir(str(run_ws)),
            patch.object(sr, "_cached_testing", return_value=sub),
            patch.object(sr, "_extract_profile_from_state", return_value=([], {})),
            patch.object(sr, "_workspace_has_tests", return_value=True),
            patch.object(sr, "_run_real_quality_gate", return_value={"passed": True}),
        ):
            sr.testing_subgraph_node(
                {"project_description": DESC, "generated_files": [], "messages": []}, {}
            )
            files = sr._snapshot_workspace_files()

        seed = sub.invoke.call_args[0][0]["messages"]
        assert f"Workspace directory: {run_ws}" in seed[-1].content
        paths = {f["path"] for f in files}
        assert any(p.endswith("calc.py") for p in paths)
        assert not any("other-run" in p for p in paths)
