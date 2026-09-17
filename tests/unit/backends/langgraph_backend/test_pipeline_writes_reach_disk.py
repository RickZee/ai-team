"""End-to-end, offline: the real LangGraph pipeline with draft-then-commit ON.

Scripted models call ``file_writer`` exactly as the prompts instruct. Before 2026-09-17
the run ended ``retry_count=3`` with pytest collecting nothing: agent writes stayed
drafts, and the QA role did not even have ``file_writer``. This test fails on either bug.
It runs the real quality gate (ruff + pytest in the run workspace).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from ai_team.backends.langgraph_backend.graphs import deployment, development, planning, testing
from ai_team.backends.langgraph_backend.graphs import subgraph_runners as sr
from ai_team.backends.langgraph_backend.graphs.main_graph import compile_main_graph
from ai_team.backends.langgraph_backend.run_session import RunSession
from ai_team.core.team_profile import load_team_profile
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

pytestmark = pytest.mark.bus_draft

CALC = "def add(a, b):\n    return a + b\n"
TEST = "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"


class _ToolFake(GenericFakeChatModel):
    def bind_tools(self, tools: Any, **kw: Any) -> _ToolFake:
        return self


def _write(path: str, content: str, i: int) -> AIMessage:
    args = {"path": path, "content": content, "overwrite": True}
    return AIMessage(content="", tool_calls=[{"name": "file_writer", "args": args, "id": f"c{i}"}])


SCRIPTS: dict[str, list[AIMessage]] = {
    "architect": [
        AIMessage(content="Architecture: one module calc.py with add(a, b) and a pytest test.")
    ],
    "fullstack_developer": [
        _write("calc.py", CALC, 1),
        AIMessage(content="Wrote calc.py with add(a, b) for the calc module."),
    ],
    "qa_engineer": [
        _write("tests/test_calc.py", TEST, 2),
        AIMessage(content="Wrote tests/test_calc.py with a pytest test for add in calc."),
    ],
}


def _fake_for(role: str, *_a: Any, **_k: Any) -> _ToolFake:
    msgs = SCRIPTS.get(role, [AIMessage(content="Deployment not required for this module.")])
    return _ToolFake(messages=iter(msgs * 3))


@pytest.mark.skipif(
    shutil.which("pytest") is None or shutil.which("ruff") is None,
    reason="quality gate needs pytest and ruff on PATH",
)
def test_prototype_pipeline_writes_reach_disk_and_tests_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_TEAM_DRAFT_WRITES", "1")
    monkeypatch.setenv("AI_TEAM_SKIP_POST_RUN", "1")
    for module in (planning, development, testing, deployment):
        monkeypatch.setattr(module, "create_chat_model_for_role", _fake_for)
    sr.reset_subgraph_cache()
    prof = load_team_profile("prototype")
    ws = tmp_path / "workspace"
    ws.mkdir()
    init = {
        "project_description": "Write a module calc.py with add(a, b) and one pytest test.",
        "project_id": "e2e-drafts",
        "current_phase": "intake",
        "phase_history": [],
        "errors": [],
        "retry_count": 0,
        "max_retries": 3,
        "messages": [],
        "generated_files": [],
        "metadata": {
            "team_profile": prof.name,
            "agents": sorted(prof.agents),
            "phases": list(prof.phases),
            "model_overrides": {},
        },
    }
    try:
        with RunSession.open(run_id="e2e-drafts", workspace_root=ws, skip_post_run=True):
            final = compile_main_graph(mode="full").invoke(
                init, {"configurable": {"thread_id": "e2e-drafts"}, "recursion_limit": 60}
            )
    finally:
        sr.reset_subgraph_cache()

    assert final["current_phase"] == "complete", final.get("phase_history")
    assert final["retry_count"] == 0
    assert final["test_results"]["passed"] is True
    run_ws = ws / "e2e-drafts"
    assert (run_ws / "calc.py").read_text(encoding="utf-8") == CALC
    assert (run_ws / "tests" / "test_calc.py").is_file()
    assert not list((run_ws / ".harness" / "drafts").glob("*.manifest.json"))
